#!/usr/bin/env python3
"""Prepare a loose-file GDK PC stage from a real Windows runtime and Partner Center identity.
This tool does not create an MSIXVC package and refuses placeholder identity values.
"""
from __future__ import annotations
import argparse, json, shutil, re, sys
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
 ap.add_argument('--runtime-dir',required=True,help='Windows x64 runtime folder containing HEXContract.exe')
 ap.add_argument('--identity',required=True,help='Partner Center identity JSON copied from the example')
 ap.add_argument('--output',default='gdk_stage/HEX_CONTRACT')
 args=ap.parse_args()
 runtime=Path(args.runtime_dir).resolve(); ident_path=Path(args.identity).resolve(); out=Path(args.output).resolve()
 if not runtime.is_dir(): raise SystemExit(f'Runtime folder missing: {runtime}')
 if not (runtime/'HEXContract.exe').is_file(): raise SystemExit('HEXContract.exe is required at runtime root.')
 ident=json.loads(ident_path.read_text(encoding='utf-8'))
 missing=[k for k in REQUIRED if not str(ident.get(k,'')).strip()]
 if missing: raise SystemExit('Missing Partner Center values: '+', '.join(missing))
 version=str(ident['version'])
 if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+',version): raise SystemExit('version must be four numeric parts, e.g. 1.0.0.0')
 if version.split('.')[-1] != '0': raise SystemExit('For MSIXVC staging keep the fourth version digit at 0; Microsoft Store reserves it.')
 text=(MS/'MicrosoftGame.config.template').read_text(encoding='utf-8')
 for token,key in TOKENS.items(): text=text.replace('{{'+token+'}}',str(ident[key]))
 if '{{' in text or '}}' in text: raise SystemExit('Unresolved MicrosoftGame.config template token remains.')
 if out.exists(): shutil.rmtree(out)
 shutil.copytree(runtime,out)
 (out/'MicrosoftGame.config').write_text(text,encoding='utf-8')
 for p in (MS/'shell_assets').glob('*.png'): shutil.copy2(p,out/p.name)
 # Sidecar retained outside MicrosoftGame.config for Xbox service/save test operators.
 sidecar={'title_id':ident['title_id'],'scid':ident['scid'],'sandbox_id':ident['sandbox_id'],'product_type':'full_game'}
 (out/'HEX_CONTRACT_XBOX_SERVICE_STAGING.json').write_text(json.dumps(sidecar,indent=2),encoding='utf-8')
 print(f'Prepared GDK loose-file stage: {out}')
 print('Next on Windows GDK: MakePkg genmap, MakePkg pack /lt for sandbox test, Wdapp install, then Submission Validator.')
if __name__=='__main__': main()
