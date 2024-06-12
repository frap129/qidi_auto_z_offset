# QIDI Auto Z-Offset support
#
# Copyright (C) 2024  Joe Maples <joe@maples.dev>
# Copyright (C) 2021  Dmitry Butyugin <dmbutyugin@google.com>
# Copyright (C) 2017-2021  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from operator import neg

from . import probe


class AutoZOffsetProbe(probe.PrinterProbe):
    def __init__(self, config, mcu_probe):
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.mcu_probe = mcu_probe
        self.speed = config.getfloat("speed", 5.0, above=0.0)
        self.lift_speed = config.getfloat("lift_speed", self.speed, above=0.0)
        self.z_offset = config.getfloat("z_offset", -0.1)
        self.probe_hop = config.getfloat("probe_hop", 5.0, minval=4.0)
        self.probe_accel = config.getfloat("probe_accel", 0.0, minval=0.0)
        self.offset_samples = config.getint("offset_samples", 3, minval=1)
        self.calibrated_z_offset = config.getfloat("calibrated_z_offset", 0.0)
        self.probe_calibrate_z = 0.0
        self.multi_probe_pending = False
        self.last_state = False
        self.last_z_result = 0.0
        self.gcode_move = self.printer.load_object(config, "gcode_move")
        # Infer Z position to move to during a probe
        if config.has_section("stepper_z"):
            zconfig = config.getsection("stepper_z")
            self.z_position = zconfig.getfloat("position_min", 0.0, note_valid=False)
        else:
            pconfig = config.getsection("printer")
            self.z_position = pconfig.getfloat(
                "minimum_z_position", 0.0, note_valid=False
            )
        # Multi-sample support (for improved accuracy)
        self.sample_count = config.getint("samples", 1, minval=1)
        self.sample_retract_dist = config.getfloat(
            "sample_retract_dist", 5.0, above=4.0
        )
        atypes = {"median": "median", "average": "average"}
        self.samples_result = config.getchoice("samples_result", atypes, "average")
        self.samples_tolerance = config.getfloat("samples_tolerance", 0.100, minval=0.0)
        self.samples_retries = config.getint("samples_tolerance_retries", 0, minval=0)
        # Register z_virtual_endstop pin
        self.printer.lookup_object("pins").register_chip("auto_z_offset", self)
        # Register homing event handlers
        self.printer.register_event_handler(
            "homing:homing_move_begin", self._handle_homing_move_begin
        )
        self.printer.register_event_handler(
            "homing:homing_move_end", self._handle_homing_move_end
        )
        self.printer.register_event_handler(
            "homing:home_rails_begin", self._handle_home_rails_begin
        )
        self.printer.register_event_handler(
            "homing:home_rails_end", self._handle_home_rails_end
        )
        self.printer.register_event_handler(
            "gcode:command_error", self._handle_command_error
        )
        # Register commands
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "AUTO_Z_PROBE",
            self.cmd_AUTO_Z_PROBE,
            desc=self.cmd_AUTO_Z_PROBE_help,
        )
        self.gcode.register_command(
            "AUTO_Z_HOME_Z",
            self.cmd_AUTO_Z_HOME_Z,
            desc=self.cmd_AUTO_Z_HOME_Z_help,
        )
        self.gcode.register_command(
            "AUTO_Z_MEASURE_OFFSET",
            self.cmd_AUTO_Z_MEASURE_OFFSET,
            desc=self.cmd_AUTO_Z_MEASURE_OFFSET_help,
        )
        self.gcode.register_command(
            "AUTO_Z_CALIBRATE",
            self.cmd_AUTO_Z_CALIBRATE,
            desc=self.cmd_AUTO_Z_CALIBRATE_help,
        )
        self.gcode.register_command(
            "AUTO_Z_LOAD_OFFSET",
            self.cmd_AUTO_Z_LOAD_OFFSET,
            desc=self.cmd_AUTO_Z_LOAD_OFFSET_help,
        )
        self.gcode.register_command(
            "AUTO_Z_SAVE_GCODE_OFFSET",
            self.cmd_AUTO_Z_SAVE_GCODE_OFFSET,
            desc=self.cmd_AUTO_Z_SAVE_GCODE_OFFSET_help,
        )

    cmd_AUTO_Z_PROBE_help = (
        "Probe Z-height at current XY position using the bed sensors"
    )

    def cmd_AUTO_Z_PROBE(self, gcmd):
        self.gcode.run_script_from_command("G0 X120 Y120")
        pos = self.run_probe(gcmd)
        self.last_z_result = neg(pos[2]) + self.z_offset
        gcmd.respond_info("Result is z=%.6f" % self.last_z_result)

    cmd_AUTO_Z_HOME_Z_help = "Home Z using the bed sensors as an endstop"

    def cmd_AUTO_Z_HOME_Z(self, gcmd):
        self.gcode.run_script_from_command("G0 X120 Y120")
        self.lift_probe()
        self.cmd_AUTO_Z_PROBE(gcmd)
        toolhead = self.printer.lookup_object("toolhead")
        toolhead.get_last_move_time()
        curpos = toolhead.get_position()
        toolhead.set_position(
            [curpos[0], curpos[1], self.z_offset, curpos[3]], homing_axes=(0, 1, 2)
        )
        self.lift_probe()

    cmd_AUTO_Z_MEASURE_OFFSET_help = (
        "Z-Offset measured by the inductive probe after AUTO_Z_HOME_Z"
    )

    def cmd_AUTO_Z_MEASURE_OFFSET(self, gcmd):
        self.cmd_AUTO_Z_HOME_Z(gcmd)
        gcmd.respond_info(
            "%s: bed sensor measured offset: z=%.6f" % (self.name, self.last_z_result)
        )
        probe = self.printer.lookup_object("probe")
        self.gcode.run_script_from_command(
            "G0 X%f Y%f" % (120 - probe.x_offset, 120 - probe.y_offset)
        )
        pos = probe.run_probe(gcmd)
        gcmd.respond_info("%s: probe measured offset: z=%.6f" % (self.name, pos[2]))
        self.lift_probe()
        return pos[2]

    cmd_AUTO_Z_CALIBRATE_help = (
        "Set the Z-Offset by averaging multiple runs of AUTO_Z_MEASURE_OFFSET"
    )

    def cmd_AUTO_Z_CALIBRATE(self, gcmd):
        offset_total = 0.0
        for _ in range(self.offset_samples):
            offset_total += self.cmd_AUTO_Z_MEASURE_OFFSET(gcmd)
        self.calibrated_z_offset = offset_total / self.offset_samples
        self.gcode.run_script_from_command(
            "SET_GCODE_OFFSET Z=%f MOVE=0" % neg(self.calibrated_z_offset)
        )

        configfile = self.printer.lookup_object("configfile")
        configfile.set(
            self.name, "calibrated_z_offset", "%.6f" % self.calibrated_z_offset
        )
        gcmd.respond_info(
            "%s: calibrated_z_offset: %.6f\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with the above and restart the printer."
            % (self.name, self.calibrated_z_offset)
        )

    cmd_AUTO_Z_LOAD_OFFSET_help = "Apply the calibrated_z_offset set in the config file"

    def cmd_AUTO_Z_LOAD_OFFSET(self, gcmd):
        gcmd.respond_info(
            "%s: calibrated_z_offset: %.6f" % (self.name, self.calibrated_z_offset)
        )
        self.gcode.run_script_from_command(
            "SET_GCODE_OFFSET Z=%f MOVE=0" % neg(self.calibrated_z_offset)
        )

    cmd_AUTO_Z_SAVE_GCODE_OFFSET_help = (
        "Save the current gcode offset for z as the new calibrated_z_offset"
    )

    def cmd_AUTO_Z_SAVE_GCODE_OFFSET(self, gcmd):
        gcode_move = self.printer.lookup_object("gcode_move")
        self.calibrated_z_offset = gcode_move.homing_position[2]
        configfile = self.printer.lookup_object("configfile")
        configfile.set(
            self.name, "calibrated_z_offset", "%.6f" % self.calibrated_z_offset
        )
        gcmd.respond_info(
            "%s: calibrated_z_offset: %.6f\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with the above and restart the printer."
            % (self.name, self.calibrated_z_offset)
        )

    def lift_probe(self):
        self.gcode.run_script_from_command("G0 Z%f F600" % self.probe_hop)


class AutoZOffsetEndstopWrapper:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.probe_accel = config.getfloat("probe_accel", 0.0, minval=0.0)
        self.probe_wrapper = probe.ProbeEndstopWrapper(config)
        # Setup prepare_gcode
        gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.prepare_gcode = gcode_macro.load_template(config, "prepare_gcode")
        # Wrappers
        self.get_mcu = self.probe_wrapper.get_mcu
        self.add_stepper = self.probe_wrapper.add_stepper
        self.get_steppers = self.probe_wrapper.get_steppers
        self.home_start = self.probe_wrapper.home_start
        self.home_wait = self.probe_wrapper.home_wait
        self.query_endstop = self.probe_wrapper.query_endstop
        self.multi_probe_end = self.probe_wrapper.multi_probe_end

    def multi_probe_begin(self):
        self.gcode.run_script_from_command(self.prepare_gcode.render())

    def probing_move(self, pos, speed):
        phoming = self.printer.lookup_object("homing")
        return phoming.probing_move(self, pos, speed)

    def probe_prepare(self, hmove):
        toolhead = self.printer.lookup_object("toolhead")
        self.probe_wrapper.probe_prepare(hmove)
        if self.probe_accel > 0.0:
            systime = self.printer.get_reactor().monotonic()
            toolhead_info = toolhead.get_status(systime)
            self.old_max_accel = toolhead_info["max_accel"]
            self.gcode.run_script_from_command("M204 S%.3f" % (self.probe_accel,))

    def probe_finish(self, hmove):
        if self.probe_accel > 0.0:
            self.gcode.run_script_from_command("M204 S%.3f" % (self.old_max_accel,))
        self.probe_wrapper.probe_finish(hmove)


def load_config(config):
    auto_z_offset = AutoZOffsetProbe(config, AutoZOffsetEndstopWrapper(config))
    config.get_printer().add_object("auto_z_offset", auto_z_offset)
    return auto_z_offset
