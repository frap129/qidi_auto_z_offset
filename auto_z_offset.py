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
        self.x_offset = config.getfloat("x_offset", 0.0)
        self.y_offset = config.getfloat("y_offset", 0.0)
        self.z_offset = config.getfloat("z_offset")
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
            "sample_retract_dist", 2.0, above=0.0
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
        # Register PROBE/QUERY_PROBE commands
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "AUTO_Z_CALIBRATE",
            self.cmd_AUTO_Z_CALIBRATE,
            desc=self.cmd_AUTO_Z_CALIBRATE_help,
        )

    cmd_AUTO_Z_CALIBRATE_help = "Probe Z-height at current XY position"

    def cmd_AUTO_Z_CALIBRATE(self, gcmd):
        pos = self.run_probe(gcmd)
        gcmd.respond_info("Result is z=%.6f" % (pos[2],))
        toolhead = self.printer.lookup_object("toolhead")
        toolhead.get_last_move_time()
        curpos = toolhead.get_position()
        toolhead.set_position(
            [curpos[0], curpos[1], neg(self.z_offset), curpos[3]], homing_axes=(0, 1, 2)
        )


class AutoZOffsetEndstopWrapper:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.probe_accel = config.getfloat("probe_accel", 0.0, minval=0.0)
        self.probe_wrapper = probe.ProbeEndstopWrapper(config)
        # Wrappers
        self.get_mcu = self.probe_wrapper.get_mcu
        self.add_stepper = self.probe_wrapper.add_stepper
        self.get_steppers = self.probe_wrapper.get_steppers
        self.home_start = self.probe_wrapper.home_start
        self.home_wait = self.probe_wrapper.home_wait
        self.query_endstop = self.probe_wrapper.query_endstop
        self.multi_probe_begin = self.probe_wrapper.multi_probe_begin
        self.multi_probe_end = self.probe_wrapper.multi_probe_end

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
    auto_z_offset = AutoZOffsetEndstopWrapper(config)
    config.get_printer().add_object(
        "auto_z_offset", AutoZOffsetProbe(config, auto_z_offset)
    )
    return auto_z_offset
