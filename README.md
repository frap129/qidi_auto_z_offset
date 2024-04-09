# Auto Z-Offset Calibration for the QIDI Q1 Pro

This is a plugin for Klipper that makes use of the QIDI Q1 Pro's bed sensors to automatically set the toolheads Z-Offset.

### Install
```
ln -s <the full path to>/auto_z_offset.py <the full path to>/klipper/klippy/extras/auto_z_offset.py
```

### Command Reference
**AUTO_Z_OFFSET**: `AUTO_Z_OFFSET` "probes" the bed

### Config Reference
```
[auto_z_offset]
pin:
#   Pin connected to the Smart Effector Z Probe output pin (pin 5). Note that
#   pullup resistor on the board is generally not required. However, if the
#   output pin is connected to the board pin with a pullup resistor, that
#   resistor must be high value (e.g. 10K Ohm or more). Some boards have a low
#   value pullup resistor on the Z probe input, which will likely result in an
#   always-triggered probe state. In this case, connect the Smart Effector to
#   a different pin on the board. This parameter is required.
#probe_accel:
#   If set, limits the acceleration of the probing moves (in mm/sec^2).
#   A sudden large acceleration at the beginning of the probing move may
#   cause spurious probe triggering, especially if the hotend is heavy.
#   To prevent that, it may be necessary to reduce the acceleration of
#   the probing moves via this parameter.
#x_offset:
#y_offset:
#   Should be left unset (or set to 0).
z_offset:
#   Offset to adjust the final z-offset value by after probing . Note that this
#   is not the same as a traditional probe's z_offset.
#speed:
#   Speed (in mm/s) of the Z axis when probing. It is recommended to start
#   with the probing speed of 20 mm/s and adjust it as necessary to improve
#   the accuracy and repeatability of the probe triggering.
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
