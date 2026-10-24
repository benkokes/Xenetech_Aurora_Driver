"""Experimental placement fit, limited to the two captured Corel XP modes."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

COREL_GRID = 'coreldraw-xp-draft'
COREL_HAIRLINE_MAX_MM = 0.5 * 25.4 / 96 + 0.000001


@dataclass(frozen=True)
class CorelLayout:
    dpi: int
    source_dpi: int = 600

    def __post_init__(self):
        if type(self.dpi) is not int or self.dpi not in (100, 167) or type(self.source_dpi) is not int or self.source_dpi != 600:
            raise ValueError('Corel reference profile requires target 100/167 DPI and source 600 DPI')

    @property
    def pitch(self):
        return 6 if self.dpi == 167 else 10

    @property
    def surface(self):
        return (5000, 3000) if self.dpi == 167 else (3000, 1800)

    @property
    def center(self):
        return (5, 3) if self.dpi == 167 else (0, 0)

    def point(self, mm, axis):
        # Undo the observed one-source-pixel displacement, then reconstruct
        # target pixel rounding and the XP page mapping. This is a reference
        # fit, not a general Corel specification or a measured machine offset.
        inches = Decimal(str(mm)) / Decimal('25.4') + Decimal(1) / self.source_dpi
        pixel = int((inches * self.dpi).quantize(Decimal(1), rounding=ROUND_HALF_UP)) - 1 - self.center[axis]
        if not 0 <= pixel <= self.surface[axis]:
            raise ValueError('Corel placement maps a cutting point outside the XP surface')
        return Decimal(pixel * self.pitch)


def from_manifest(doc, page):
    meta = doc.get('corel_xp_compatibility')
    if not isinstance(meta, dict) or meta.get('model') != 'coreldraw-x7-to-xp11-flatbed-v1' or meta.get('validation') != 'reference_fit_not_physical_calibration':
        raise ValueError('Missing explicit Corel XP reference profile provenance')
    if meta.get('target_dpi') != doc.get('dpi') or type(meta.get('target_dpi')) is not int:
        raise ValueError('Corel target DPI provenance differs from raster DPI')
    if abs(page['width_mm'] - 762) > 1e-6 or abs(page['height_mm'] - 457.2) > 1e-6:
        raise ValueError('Corel reference profile requires a 30 x 18 inch page')
    return CorelLayout(doc['dpi'], meta.get('source_printer_dpi'))
