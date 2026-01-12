# 3.7V Battery Patches for Pebble Watches

## Overview

This patcher supports 3.7V LiPo replacement batteries (like iFixit batteries) for Pebble watches that originally shipped with 3.8V batteries.

## Supported Devices

| Flag | Device | Original Battery | Replacement |
|------|--------|------------------|-------------|
| `--silk-3v7` | Pebble 2 | 3.8V | 3.7V LiPo |
| `--snowy-3v7` | Pebble Time Steel | 3.8V | 3.7V LiPo |
| `--snowy-dvt-3v7` | Pebble Time | 3.8V | 3.7V LiPo |

## What Gets Patched

### 1. Battery Percentage Tables

Original 3.8V curve:
- 100% = 4250mV
- 0% = 3300mV

Patched 3.7V curve (Joshua's proven silk values):
- 100% = 4120mV
- 90% = 4080mV
- 80% = 4000mV
- 70% = 3925mV
- 60% = 3860mV
- 50% = 3810mV
- 40% = 3775mV
- 30% = 3745mV
- 20% = 3710mV
- 10% = 3670mV
- 5% = 3600mV
- 2% = 3410mV
- 0% = 3100mV

#### 3.7V Charging Curve

```
2%  @ 3820mV
5%  @ 3900mV
10% @ 3950mV
20% @ 3980mV
30% @ 4020mV
40% @ 4060mV
50% @ 4080mV
60% @ 4110mV
70% @ 4120mV
```

**Why it caps at 70%:** The PMIC terminates at 4.20V. With any charging polarization offset, showing 100% would require a voltage above termination. The curve is compressed from Pebble's original 400mV span (3850-4250mV) to 300mV (3820-4120mV).

**Offset comparison to original Pebble 3.8V:**

| SoC | Pebble 3.8V Offset | 3.7V Offset | Difference |
|-----|-------------------|-------------|------------|
| 2%  | 385mV | 410mV | +25mV |
| 5%  | 320mV | 300mV | -20mV |
| 10% | 315mV | 280mV | -35mV |
| 20% | 315mV | 270mV | -45mV |
| 30% | 330mV | 275mV | -55mV |
| 40% | 350mV | 285mV | -65mV |
| 50% | 345mV | 270mV | -75mV |
| 60% | 340mV | 250mV | -90mV |
| 70% | 295mV | 195mV | -100mV |

Differences of 20-75mV in the usable range are within normal battery variance. The 100mV difference at 70% is due to the voltage ceiling constraint.

**Offset pattern matches CC/CV charging physics:**
- High offset at low SoC (410mV at 2%): CC phase, high current
- Medium offset mid-range (270-285mV): bulk CC charging
- Low offset at high SoC (195mV at 70%): approaching CV phase, current tapering

**Expected UX during charging:**
- CC phase (0-70%): percentage rises normally
- CV phase: plateaus around 70-80%
- When complete: jumps to 100% (switches to discharge curve)
- The last 30% is slow and adds less capacity — the plateau UX matches the physics
- Pebble displays in 10% increments (except 2%, 5%), so small errors are invisible

### 2. PMIC Charge Termination (FC Fix)

The MAX14690 PMIC controls charging. Original firmware targets 4.30V, which a 3.7V battery can't reach - so FC (Fully Charged) never appears.

**Patches applied:**
- HACK register: 0xCD (4.35V) → 0xC7 (4.20V)
- CHG_CNTL_A register: 0xCB (4.30V) → 0xC7 (4.20V)

Both must be patched because `prv_config_charger()` writes the HACK value first, cycles the charger, then writes the real config.

### 3. 15-Minute Maintain Timeout

After reaching charge termination, the PMIC enters "maintain mode" for 15 minutes before reporting "Done". FC only appears after this phase completes.

The test branch (`claude/pts-fc-test-YVWoU`) has an additional patch to disable this timeout for instant FC:
- CH_TMR register: 0x18 (15 min) → 0x08 (0 min)

This is optional - the main branches keep the 15-minute timeout for safety.

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

- 3100mV (3.1V) for 0% is safe - 3.7V LiPo cells can safely discharge to ~3.0V
- 4120mV (4.12V) for 100% is conservative - 3.7V LiPo max is 4.20V
- These values match Joshua's proven Pebble 2 curve (`--silk-3v7`)

## Technical Details

### Battery Table Format

Each entry is 4 bytes (little-endian):
```
[pct_lo] [pct_hi] [mv_lo] [mv_hi]
```

Example: `64 00 18 10` = 100% @ 0x1018 = 4120mV

### PMIC Register Values

CHG_CNTL_A (0x0A) bits 3:1 control charge voltage:
- 0b011 = 4.20V (0xC7 with other bits)
- 0b101 = 4.30V (0xCB with other bits)
- 0b110 = 4.35V (0xCD with other bits)

### Why Both HACK and Real Config Need Patching

From `prv_config_charger()`:
1. HACK writes 4.35V to CHG_CNTL_A
2. Charger cycles (off/on)
3. Real config writes 4.30V to CHG_CNTL_A

If only real config is patched, the PMIC enters charging mode during the HACK phase (battery < 4.35V target) and doesn't re-evaluate when real config is written.

## Source Files

- `/home/user/pebble-firmware/src/fw/drivers/pmic/max14690_pmic.c` - PMIC driver
- `/home/user/pebble-firmware/src/fw/services/common/battery/voltage/battery_curve.c` - Battery curves
- `/home/user/pebble-firmware/src/fw/shell/normal/battery_ui_fsm.c` - FC trigger logic
