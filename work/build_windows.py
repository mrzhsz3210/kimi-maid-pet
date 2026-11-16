from pathlib import Path
import sys,subprocess,shutil,json
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'.build-tools'));sys.path.insert(0,str(root/'app'))
from version import VERSION
import PyInstaller.__main__
from PyInstaller.utils.hooks import collect_all

datas=[];binaries=[];hiddenimports=[]
for module in ('sherpa_onnx','sounddevice','pypinyin'):
    module_datas,module_binaries,module_hiddenimports=collect_all(module)
    datas+=module_datas;binaries+=module_binaries;hiddenimports+=module_hiddenimports
args=['--noconfirm','--clean','--onedir','--windowed','--name','KimiMaidPet','--distpath',str(root/'发布包'/f'build-v{VERSION}'),'--workpath',str(root/'.build'/f'work-v{VERSION}'),'--specpath',str(root/'.build'),'--exclude-module','scipy','--exclude-module','matplotlib','--exclude-module','tkinter','--exclude-module','PyQt5','--exclude-module','PyQt6','--hidden-import','autostart','--hidden-import','selftest','--hidden-import','version','--hidden-import','voice_input','--hidden-import','voice_models','--hidden-import','voice_ui']
for item in datas:args+=['--add-data',f'{item[0]};{item[1]}']
for item in binaries:args+=['--add-binary',f'{item[0]};{item[1]}']
for item in hiddenimports:args+=['--hidden-import',item]
PyInstaller.__main__.run(args+[str(root/'app/pet.py')])
