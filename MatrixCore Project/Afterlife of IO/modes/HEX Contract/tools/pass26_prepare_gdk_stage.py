#!/usr/bin/env python3
"""Prepare the Pass 26 Microsoft GDK stage from a tested Windows runtime.

Requires real Partner Center identity and a native bridge build. Does not itself
create or claim an MSIXVC; package creation remains a Windows GDK operation.
"""
from __future__ import annotations
import argparse, json, shutil, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MS=ROOT/'platform'/'microsoft'
REQUIRED=('identity_name','identity_publisher','publisher_display_name','store_id','msa_app_id','title_id','scid','sandbox_id','version')
TOKENS={
 'IDENTITY_NAME':'identity_name','IDENTITY_PUBLISHER':'identity_publisher','PUBLISHER_DISPLAY_NAME':'publisher_display_name',
 'STORE_ID':'store_id','MSA_APP_ID':'msa_app_id','TITLE_ID':'title_id','VERSION':'version'
}

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--runtime-dir',required=True)
 ap.add_argument('--bridge-dir',required=True,help='native_bridge/build folder containing HEXContractGDKBridge.dll')
 ap.add_argument('--identity',required=True)
 ap.add_argument('--output',default='gdk_stage/HEX_CONTRACT')
 args=ap.parse_args()
 runtime=Path(args.runtime_dir).resolve(); bridge=Path(args.bridge_dir).resolve(); ident_path=Path(args.identity).resolve(); out=Path(args.output).resolve()
 if not (runtime/'HEXContract.exe').is_file(): raise SystemExit('HEXContract.exe is required at runtime root.')
 if not (bridge/'HEXContractGDKBridge.dll').is_file(): raise SystemExit('HEXContractGDKBridge.dll is required. Build the native GDK bridge first.')
 ident=json.loads(ident_path.read_text(encoding='utf-8'))
 missing=[k for k in REQUIRED if not str(ident.get(k,'')).strip()]
 if missing: raise SystemExit('Missing Partner Center values: '+', '.join(missing))
 version=str(ident['version'])
 if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+',version): raise SystemExit('version must be four numeric parts')
 if version.split('.')[-1] != '0': raise SystemExit('MSIXVC/MSIXVC2 reserves the fourth version digit; keep it at 0.')
 text=(MS/'MicrosoftGame.config.template').read_text(encoding='utf-8')
 for token,key in TOKENS.items(): text=text.replace('{{'+token+'}}',str(ident[key]))
 if '{{' in text or '}}' in text: raise SystemExit('Unresolved MicrosoftGame.config token remains.')
 if out.exists(): shutil.rmtree(out)
 shutil.copytree(runtime,out)
 shutil.copy2(bridge/'HEXContractGDKBridge.dll', out/'HEXContractGDKBridge.dll')
 dep_manifest=bridge/'GDK_RUNTIME_DEPENDENCIES.txt'
 if dep_manifest.is_file():
  for name in dep_manifest.read_text(encoding='utf-8').splitlines():
   name=name.strip()
   if name and (bridge/name).is_file(): shutil.copy2(bridge/name,out/name)
 (out/'MicrosoftGame.config').write_text(text,encoding='utf-8')
 for p in (MS/'shell_assets').glob('*.png'): shutil.copy2(p,out/p.name)
 sidecar={
  'title_id':str(ident['title_id']), 'scid':str(ident['scid']), 'sandbox_id':str(ident['sandbox_id']),
  'product_type':'full_game', 'native_bridge_enabled':True, 'save_container':'HEXContract',
  'achievement_mode':'title_managed', 'package_format':'MSIXVC'
 }
 (out/'HEX_CONTRACT_XBOX_SERVICE_STAGING.json').write_text(json.dumps(sidecar,indent=2),encoding='utf-8')
 print(f'Prepared Pass 26 GDK loose-file stage: {out}')
 print('Next: MakePkg genmap -> MakePkg pack /lt -> wdapp install -> native acceptance harness -> Submission Validator -> /lk retail package.')
if __name__=='__main__': main()
