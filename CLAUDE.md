# 3.7V Battery Patches for Pebble Watches

## Overview

This patcher supports 3.7V LiPo replacement batteries (like iFixit batteries) for Pebble watches that originally shipped with 3.8V batteries. The patches modify battery percentage curves and PMIC charge termination to work correctly with the lower voltage chemistry.

## Supported Devices

| Flag | Device | Platform | Original Battery | Replacement |
|------|--------|----------|------------------|-------------|
| `--silk-3v7` | Pebble 2 | SILK | 3.8V | 3.7V LiPo |
| `--snowy-3v7` | Pebble Time Steel | SNOWY_S3 | 3.8V | 3.7V LiPo |
| `--snowy-dvt-3v7` | Pebble Time | SNOWY | 3.8V | 3.7V LiPo |

## Battery Chemistry Differences

### 3.8V vs 3.7V LiPo Cells

| Property | 3.8V (Original) | 3.7V (Replacement) |
|----------|-----------------|---------------------|
| Full charge | 4.35V | 4.20V |
| Nominal | 3.80V | 3.70V |
| Cutoff | 3.30V | 3.00V |
| 100% threshold | 4250mV | 4120mV |

The original firmware expects batteries to charge to 4.35V. A 3.7V replacement battery only reaches ~4.20V, causing:
1. Battery percentage never shows 100%
2. FC (Fully Charged) indicator never appears

## What Gets Patched

### 1. Discharge Curve (Battery Percentage When Not Charging)

Uses Joshua's proven silk 3.7V values, validated on Pebble 2 devices. These values also match PLATFORM_TINTIN in the Pebble firmware source.

**Original 3.8V curve (PTS/snowy_s3):**
| % | mV | Hex |
|---|-----|-----|
| 0 | 3300 | e4 0c |
| 2 | 3465 | 89 0d |
| 5 | 3615 | 1f 0e |
| 10 | 3685 | 65 0e |
| 20 | 3725 | 8d 0e |
| 30 | 3760 | b0 0e |
| 40 | 3795 | d3 0e |
| 50 | 3830 | f6 0e |
| 60 | 3885 | 2d 0f |
| 70 | 3955 | 73 0f |
| 80 | 4065 | e1 0f |
| 90 | 4160 | 40 10 |
| 100 | 4250 | 9a 10 |

**Patched 3.7V curve (Joshua's silk values):**
| % | mV | Hex |
|---|-----|-----|
| 0 | 3100 | 1c 0c |
| 2 | 3410 | 52 0d |
| 5 | 3600 | 10 0e |
| 10 | 3670 | 56 0e |
| 20 | 3710 | 7e 0e |
| 30 | 3745 | a1 0e |
| 40 | 3775 | bf 0e |
| 50 | 3810 | e2 0e |
| 60 | 3860 | 14 0f |
| 70 | 3925 | 55 0f |
| 80 | 4000 | a0 0f |
| 90 | 4080 | f0 0f |
| 100 | 4120 | 18 10 |

### 2. Charging Curve (Battery Percentage While Charging)

While charging, battery voltage is higher due to IR drop (current x internal resistance). The firmware uses a separate curve for charging that accounts for this offset.

**Original 3.8V charging curve (PTS - 2% to 70%):**
| % | mV | IR offset |
|---|-----|-----------|
| 2 | 3850 | +385mV |
| 5 | 3935 | +320mV |
| 10 | 4000 | +315mV |
| 20 | 4040 | +315mV |
| 30 | 4090 | +330mV |
| 40 | 4145 | +350mV |
| 50 | 4175 | +345mV |
| 60 | 4225 | +340mV |
| 70 | 4250 | +295mV |

**Patched 3.7V charging curve (preserves IR offset relationship):**
| % | mV | Hex |
|---|-----|-----|
| 2 | 3820 | ec 0e |
| 5 | 3900 | 3c 0f |
| 10 | 3950 | 6e 0f |
| 20 | 3980 | 8c 0f |
| 30 | 4020 | b4 0f |
| 40 | 4060 | dc 0f |
| 50 | 4080 | f0 0f |
| 60 | 4110 | 0e 10 |
| 70 | 4120 | 18 10 |

**Note:** Charging curve only goes to 70% because FC (Fully Charged) is triggered by PMIC hardware, not by reaching 100% in the percentage table.

### 3. PMIC Charge Termination (FC Fix)

The MAX14690 PMIC controls charging via I2C register CHG_CNTL_A (0x0A). The charge termination voltage is set in bits 6:4.

**Register values:**
| Bits 6:4 | Voltage | Full byte (with other bits) |
|----------|---------|------------------------------|
| 0b110 | 4.35V | 0xCD |
| 0b101 | 4.30V | 0xCB |
| 0b011 | 4.20V | 0xC7 |

**Patches applied:**
1. **HACK register**: 0xCD -> 0xC7 (4.35V -> 4.20V)
2. **CHG_CNTL_A register**: 0xCB -> 0xC7 (4.30V -> 4.20V)

**Why both patches are needed:**

From `prv_config_charger()` in the firmware:
```
1. Write 0xCD (4.35V) to CHG_CNTL_A    <- HACK
2. Turn charger OFF
3. Turn charger ON                      <- PMIC evaluates: battery vs target
4. Write 0xCB (4.30V) to CHG_CNTL_A    <- Real config
```

If only step 4 is patched:
- At step 3, PMIC sees battery (4.0V) < target (4.35V) -> enters CHARGING mode
- At step 4, PMIC is already in charging mode, doesn't re-evaluate
- Result: FC never appears

With both patched:
- At step 3, PMIC sees battery (4.0V) < target (4.20V) -> enters CHARGING mode
- When battery reaches 4.20V, PMIC transitions to DONE state
- Result: FC appears correctly

### 4. 15-Minute Maintain Timeout (Optional)

After reaching charge termination voltage, the PMIC enters "maintain mode" for 15 minutes before reporting "Done" to the firmware. This is controlled by CH_TMR register.

**Test branch only** (`claude/pts-fc-test-YVWoU`):
- CH_TMR register: 0x18 (15 min) -> 0x08 (0 min)
- Provides instant FC for testing
- Main branches keep the 15-minute timeout for battery safety

## Binary Format

### Battery Table Entry Format

Each entry is 4 bytes (little-endian):
```
[percent_lo] [percent_hi] [millivolts_lo] [millivolts_hi]
```

Example: `64 00 18 10`
- Percent: 0x0064 = 100
- Millivolts: 0x1018 = 4120mV

### ARM Thumb Instruction Patching

PMIC register writes are ARM Thumb MOVS instructions:
```
0a 20    ; MOVS R0, #0x0A  (register address)
cb 21    ; MOVS R1, #0xCB  (register value)
97 f7    ; BL prv_write_register
```

We patch the immediate value in the second instruction.

## Usage

```bash
# Pebble Time Steel
./patchpbz.py -v v4.4.3-rbl-3v7 -b --snowy-3v7 -t tzdata.bin.reso --license rbl-license.txt \
    Pebble-4.3-snowy_s3.pbz out/Pebble-4.4.3-rbl-snowy_s3-3v7.pbz

# Pebble Time
./patchpbz.py -v v4.4.3-rbl-3v7 -b --snowy-dvt-3v7 -t tzdata.bin.reso --license rbl-license.txt \
    Pebble-4.3-snowy_dvt.pbz out/Pebble-4.4.3-rbl-snowy_dvt-3v7.pbz

# Pebble 2
./patchpbz.py -v v4.4.3-rbl-3v7 -b --silk-3v7 -t tzdata.bin.reso --license rbl-license.txt \
    Pebble-4.3-silk.pbz out/Pebble-4.4.3-rbl-silk-3v7.pbz
```

## Pre-built Firmware

- `out/Pebble-4.4.3-rbl-snowy_s3-3v7.pbz` - Pebble Time Steel
- `out/Pebble-4.4.3-rbl-snowy_dvt-3v7.pbz` - Pebble Time

## Safety Notes

- **0% = 3100mV (3.1V)**: Safe - 3.7V LiPo cells can discharge to ~3.0V without damage
- **100% = 4120mV (4.12V)**: Conservative - 3.7V LiPo max is 4.20V, leaving margin
- **Termination at 4.20V**: Standard safe charge voltage for 3.7V LiPo chemistry
- **15-minute maintain**: Ensures battery is fully topped off before showing FC

## Firmware Source References

### Battery Curves
`/home/user/pebble-firmware/src/fw/services/common/battery/voltage/battery_curve.c`

Platform definitions:
- `PLATFORM_TINTIN` - Classic Pebble (has 3.7V curves - used as reference)
- `BOARD_SNOWY_S3` - Pebble Time Steel (3.8V curves)
- `PLATFORM_SNOWY` - Pebble Time (3.8V curves)
- `PLATFORM_SILK` - Pebble 2 (3.8V curves, Joshua's patch targets this)

### PMIC Driver
`/home/user/pebble-firmware/src/fw/drivers/pmic/max14690_pmic.c`

Key functions:
- `prv_config_charger()` - Configures charge voltage registers
- `prv_write_register()` - I2C write to PMIC

### Battery UI
`/home/user/pebble-firmware/src/fw/shell/normal/battery_ui_fsm.c`

- State machine for battery UI (charging, FC, etc.)
- FC triggered by PMIC status register, not percentage

## Troubleshooting

### Battery percentage stuck at low value
- Check discharge curve was patched correctly
- Verify pattern match in patcher output (no "WARNING" messages)

### FC never appears
- Ensure BOTH PMIC patches applied (HACK and real config)
- Wait 15 minutes after charge termination (maintain timeout)
- Check PMIC patch applied (look for 0xC7 pattern in firmware)

### Percentage jumps during charging
- Normal behavior due to IR drop difference between charging and discharging
- Charging curve accounts for this, but transitions can cause visible jumps

## Version History

- **v4.4.3-rbl-3v7**: Initial 3.7V support with FC fix
- Based on Rebble v4.3 firmware with timezone and license patches
