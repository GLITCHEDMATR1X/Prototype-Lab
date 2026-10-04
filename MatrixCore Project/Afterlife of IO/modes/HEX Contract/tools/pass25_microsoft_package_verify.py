"""Pass 25 Microsoft full-title package/save readiness verifier. No GDK import required."""
from __future__ import annotations
from pathlib import Path
import hashlib, json, re, sys, xml.etree.ElementTree as ET
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/mnt/data/hex_pass24_base/HEX Contract')
MS=ROOT/'platform/microsoft'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=json.loads((MS/'package_profile.json').read_text())
 t=(MS/'MicrosoftGame.config.template').read_text()
 checks={}
 checks['full_game_not_demo']=p['product_type']=='full_game' and p['demo'] is False and p['trial'] is False
 checks['pc_x64_target']=p['target']=='Gaming.Desktop.x64' and p['target_device_family']=='PC' and p['architecture']=='x64'
 checks['release_format_msixvc']=p['package_format_release_target']=='MSIXVC' and p['package_format_preview_not_for_public_cert']=='MSIXVC2'
 checks['no_fake_root_config']=not (ROOT/'MicrosoftGame.config').exists()
 checks['required_template_tokens']=all('{{'+x+'}}' in t for x in ('IDENTITY_NAME','IDENTITY_PUBLISHER','PUBLISHER_DISPLAY_NAME','STORE_ID','MSA_APP_ID','TITLE_ID','VERSION'))
 sample={'IDENTITY_NAME':'CN=HEXCONTRACT.TEST','IDENTITY_PUBLISHER':'CN=TEST','PUBLISHER_DISPLAY_NAME':'GLITCHED MATRIX','STORE_ID':'9TEST','MSA_APP_ID':'0000000000000000','TITLE_ID':'00000000','VERSION':'1.0.0.0'}
 r=t
 for k,v in sample.items(): r=r.replace('{{'+k+'}}',v)
 try:
  root=ET.fromstring(r); exe=root.find('./ExecutableList/Executable'); shell=root.find('./ShellVisuals')
  checks['template_xml_parses']=root.tag=='Game' and root.attrib.get('configVersion')=='1'
  checks['identity_and_service_elements']=root.find('Identity') is not None and root.find('StoreId') is not None and root.find('MSAAppId') is not None and root.find('TitleId') is not None
  checks['executable_contract']=exe is not None and exe.attrib.get('Name')=='HEXContract.exe' and exe.attrib.get('TargetDeviceFamily')=='PC' and exe.attrib.get('Architecture')=='x64'
  checks['shell_visuals_contract']=shell is not None and shell.attrib.get('SplashScreenImage')=='SplashScreen.png'
 except Exception:
  checks['template_xml_parses']=checks['identity_and_service_elements']=checks['executable_contract']=checks['shell_visuals_contract']=False
 sizes=p['shell_assets']; size_ok={}
 for n,s in sizes.items():
  path=MS/'shell_assets'/n
  try: size_ok[n]=path.is_file() and list(Image.open(path).size)==s and Image.open(path).format=='PNG'
  except: size_ok[n]=False
 checks['shell_asset_dimensions']=all(size_ok.values())
 checks['stage_generator_refuses_missing_identity']='Missing Partner Center values' in (ROOT/'tools/pass25_prepare_gdk_stage.py').read_text()
 bat=(MS/'PREPARE_AND_PACK_GDK_TEST.bat').read_text()
 retail=(MS/'PACK_GDK_RETAIL_LK.bat').read_text()
 checks['gdk_test_pack_commands']=all(x in bat for x in ('MakePkg genmap','MakePkg pack','/lt','/nogameos','/pc'))
 checks['retail_lk_separated']='/lk' in retail and '/lt' not in retail
 checks['save_root_seam_preserved']=sha(ROOT/'game/save_paths.py')==sha(BASE/'game/save_paths.py') and 'XGameSaveFilesGetFolderWithUIAsync' in (MS/'XGAMESAVEFILES_BRIDGE_CONTRACT.md').read_text()
 frozen=('main.py','game/data.py','game/sim.py','game/actors.py','game/actor_visuals.py','game/audio.py','game/world_data.py','game/world.py','game/achievements.py','game/platform_input.py','game/save_paths.py','platform/xbox/achievements_manifest.json','platform/xbox/controller_mapping.json')
 frozen_result={x:sha(ROOT/x)==sha(BASE/x) for x in frozen}
 checks['pass24_gameplay_achievements_controller_frozen']=all(frozen_result.values())
 checks['profile_schema_v9']='"profile_version": 9' in (ROOT/'game/app.py').read_text()
 checks['source_no_forbidden_cache']=not any(p.name=='__pycache__' or p.suffix=='.pyc' for p in ROOT.rglob('*'))
 ok=all(checks.values())
 out={'pass25_microsoft_full_title_readiness':'PASS' if ok else 'FAIL','checks':checks,'shell_assets':size_ok,'frozen_pass24_modules':frozen_result,'product_type':'full_game','profile_version':9,'native_gdk_claimed':False,'native_msixvc_claimed':False,'native_xgamesavefiles_claimed':False,'environment_limits':['Microsoft GDK unavailable','Windows runtime unavailable','pygame-ce unavailable','Panda3D unavailable from package mirror']}
 dest=ROOT/'verification/reports/pass25_microsoft_package_readiness.json'; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(out,indent=2))
 print(json.dumps(out,indent=2)); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
