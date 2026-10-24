"""Generate the unsigned, data-only Aurora v4 printer package for validation.

Does not install a driver, change certificates, start a service, or send a job.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from aurora_jobserver.printer_settings import FEATURES, decode, default_selection


ROOT = Path(__file__).resolve().parents[1]


def gpd(classic_settings=False):
    text = (ROOT / 'frontend/driver/Aurora.gpd.in').read_text(encoding='utf-8')
    for feature in FEATURES:
        text += ('\n*Feature: '+feature.key+'\n{\n    *Name: "'+feature.label+'"\n'
                 '    *FeatureType: DOC_PROPERTY\n    *DefaultOption: '+feature.default+'\n')
        options = feature.options + ((('Custom', 'Value from Aurora Properties'),) if classic_settings and feature.key != 'AuroraAutostart' else ())
        for keyword, label in options:
            text += '    *Option: '+keyword+'\n    {\n        *Name: "'+label+'"\n    }\n'
        text += '}\n'
    return text


def build(destination, printer_ui=None, classic_settings=False):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name in ('Aurora.inf','Aurora-manifest.ini','Aurora-pipelineconfig.xml'):
        shutil.copyfile(ROOT / 'frontend/driver' / name, destination / name)
    if classic_settings:
        if printer_ui is None:
            raise ValueError('Complete preferences require the native Properties extension')
        files = ('AuroraSettings.js','Aurora-devmode.xml')
        for name in files:
            shutil.copyfile(ROOT / 'frontend/driver' / name, destination / name)
        inf = (destination / 'Aurora.inf').read_text()
        inf = inf.replace('0.4.2.0','0.5.3.0').replace('[AuroraFiles]\n','[AuroraFiles]\n'+'\n'.join(files)+'\n')
        inf = inf.replace('[SourceDisksFiles]\n','[SourceDisksFiles]\n'+'\n'.join(name+'=1' for name in files)+'\n')
        (destination / 'Aurora.inf').write_text(inf,encoding='ascii')
        manifest = (destination / 'Aurora-manifest.ini').read_text()
        manifest = manifest.replace('[DriverConfig]\n','[DriverConfig]\nConstraintScript=AuroraSettings.js\nDevModeMap=Aurora-devmode.xml\n')
        (destination / 'Aurora-manifest.ini').write_text(manifest,encoding='ascii')
    if printer_ui is not None:
        printer_ui = Path(printer_ui)
        binaries = ('Aurora.PrinterProperties.exe', 'Interop.PrinterExtensionLib.dll')
        for name in binaries:
            shutil.copyfile(printer_ui / name, destination / name)
        inf = (destination / 'Aurora.inf').read_text()
        inf = inf.replace('[AuroraFiles]\n', '[AuroraFiles]\n' + '\n'.join(binaries) + '\n')
        inf = inf.replace('[SourceDisksFiles]\n', '[SourceDisksFiles]\n' +
                          '\n'.join(name + '=1' for name in binaries) + '\n')
        (destination / 'Aurora.inf').write_text(inf, encoding='ascii')
        with (destination / 'Aurora-manifest.ini').open('a', encoding='ascii') as manifest:
            manifest.write('\n[PrinterExtensions]\nPrintPreferences=Aurora.PrinterProperties.exe,'
                           '{12CE902C-DD91-41A9-AD32-F51B6DE8C15B}\n')
    (destination / 'Aurora.gpd').write_bytes(gpd(classic_settings).replace('\r\n','\n').replace('\n','\r\n').encode('ascii'))
    result = {'schema_version':1, 'state':'unsigned_source_package_not_installed',
              'native_gpd_validation':'pending', 'catalog_signing':'pending',
              'driver_name':'Aurora JobServer XPS Bridge',
              'printer_driver_id':'{72F09BB3-5810-4A7E-9960-69E4151CDF30}',
              'complete_preferences':classic_settings,
              'default_settings':decode(default_selection()),
              'files':{path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sorted(destination.iterdir())}}
    (destination / 'package-build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--printer-ui', type=Path, help='Built native Properties EXE and COM metadata directory')
    parser.add_argument('--classic-settings',action='store_true',help='Include the full per-job preferences transport')
    args = parser.parse_args()
    print(json.dumps(build(args.destination, args.printer_ui, args.classic_settings),indent=2))


if __name__ == '__main__':
    main()
