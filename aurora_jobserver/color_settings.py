"""Shared palette validation for the offline color raster/vector models.

Legacy ranges here model XP files only; they do not change delivery limits.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .classic_settings import NAMES, RGB


@dataclass(frozen=True)
class ColorProcess:
    speed_native: int
    power_percent: int
    ppi: int


def decimal_number(value, label, low, high, scale):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('Invalid ' + label)
    try:
        result = Decimal(str(value))
        if (not result.is_finite() or not low <= result <= high
                or result * scale != (result * scale).to_integral_value()):
            raise ValueError('Invalid range or precision for ' + label)
    except InvalidOperation as error:
        raise ValueError('Invalid ' + label) from error
    return result


def parse_palette(records):
    if not isinstance(records, (list, tuple)) or len(records) != 16:
        raise ValueError('Expected the original 16-color palette')
    result = []
    for index, record in enumerate(records):
        required = {'Name', 'R', 'G', 'B', 'Enabled', 'PowerPercent', 'SpeedIps', 'Ppi'}
        if not isinstance(record, dict) or set(record) != required:
            raise ValueError('Incomplete color record')
        expected = [(RGB[index] >> shift) & 255 for shift in (16, 8, 0)]
        channels = [record[channel] for channel in ('R', 'G', 'B')]
        if (record['Name'] != NAMES[index] or channels != expected
                or any(type(channel) is not int for channel in channels)):
            raise ValueError('Original palette identity changed')
        if type(record['Enabled']) is not bool:
            raise ValueError('Color enable must be an explicit boolean')
        speed = decimal_number(record['SpeedIps'], 'color speed', Decimal('.001'), 150, 1000)
        power = decimal_number(record['PowerPercent'], 'color power', 0, 100, 100)
        if power != power.to_integral_value():
            raise ValueError('Fractional color power requires independent XP evidence')
        ppi = record['Ppi']
        if type(ppi) is not int or not 5 <= ppi <= 1000:
            raise ValueError('Invalid color PPI')
        result.append(ColorProcess(int(speed * 1000), int(power) if record['Enabled'] else 0, ppi))
    return tuple(result)
