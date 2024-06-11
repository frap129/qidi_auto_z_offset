# Auto Z-Offset Calibration for the QIDI Q1 Pro

This is a plugin for Klipper that makes use of the QIDI Q1 Pro's bed sensors to automatically set the toolheads Z-Offset.

⚠️ **NOTE** ⚠️
This should not be used at the begining of a print! If the bed sensors fail to trigger, or trigger to late, you can end up
grinding the nozzle into the bed when you got to start a print. Instead, you should run `AUTO_Z_CALIBRATE_OFFSET` prior to
your first print, move Z to 0, and verify that you can slide a piece of paper under the nozzle.

### Install
```
cd ~
git clone https://github.com/frap129/qidi_auto_z_offset
ln -s ~/qidi_auto_z_offset/auto_z_offset.py ~/klipper/klippy/extras/auto_z_offset.py
```

### Command Reference
**AUTO_Z_PROBE**: Probe Z-height at current XY position using the bed sensors
**AUTO_Z_HOME_Z**: Home Z using the bed sensors as an endstop
**AUTO_Z_MEASURE_OFFSET** Z-Offset measured by the inductive probe after AUTO_Z_HOME_Z
**AUTO_Z_CALIBRATE**: Set the Z-Offset by averaging multiple runs of AUTO_Z_MEASURE_OFFSET

### Config Reference
```
[auto_z_offset]
pin:
#   Pin connected to the Auto Z Offset output pin. This parameter is required.
z_offset:
#   The z positon that triggering the bed sensors corre.
#   default is -0.1
prepare_gcode:
#   gcode script to run before probing with auto_z_offset. This is required, and an
#   example script is provided below.
#probe_accel:
#   If set, limits the acceleration of the probing moves (in mm/sec^2).
#   A sudden large acceleration at the beginning of the probing move may
#   cause spurious probe triggering, especially if the hotend is heavy.
#   To prevent that, it may be necessary to reduce the acceleration of
#   the probing moves via this parameter.
#probe_hop:
#   The amount to hop between probing with bed sensors and probing with probe.
#   default is 5.0, min is 4.0 to avoid triggering the probe early
#offset_samples:
#   The number of times to probe with bed sensors and inductive probe. Note,
#   this is not the same as `samples`. 
#   default is 3
#speed:
#samples:
#sample_retract_dist:
#samples_result:
#samples_tolerance:
#samples_tolerance_retries:
#activate_gcode:
#deactivate_gcode:
#deactivate_on_each_sample:
#   See the "probe" section for more information on the parameters above.
```

### Example Configuration from OpenQ1
This example config also includes the control pin for the bed sensors and the config for the inductive probe. Use them as shown for the best compatiblity.
```
[output_pin bed_sensor]
pin: !U_1:PA14
value:0

[probe]
pin:!gpio21
x_offset: 17.6
y_offset: 4.4
z_offset: 0.0
speed:10
samples: 3
samples_result: average
sample_retract_dist: 4.0
samples_tolerance: 0.05
samples_tolerance_retries: 5

[auto_z_offset]
pin: U_1:PC1
z_offset: -0.1
speed: 10
probe_accel: 50
samples: 3
samples_result: average
samples_tolerance: 0.05
samples_tolerance_retries: 5
prepare_gcode:
    SET_PIN PIN=bed_sensor VALUE=0
    G91
    {% set i = 4 %}
    {% for iteration in range(i|int) %}
        G1 Z1 F900
        G1 Z-1 F900
    {% endfor %}
    G90
    SET_PIN PIN=bed_sensor VALUE=1
```

