# Auto Z-Offset Calibration for the QIDI Q1 Pro

This is a plugin for Klipper that makes use of the QIDI Q1 Pro's bed sensors to automatically set the toolheads Z-Offset.

### Install
```
ln -s <path to>/auto_z_offset.py <path to>/klipper/klippy/extras/auto_z_offset.py
```

### Command Reference
**AUTO_Z_CALIBRATE**: `AUTO_Z_CALIBRATE` "probes" the bed to measure z-offset

### Config Reference
```
[auto_z_offset]
pin:
#   Pin connected to the Auto Z Offset output pin. This parameter is required.
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
