from pathlib import Path
import ast, json, math, textwrap, types
from panda3d.core import (
    AmbientLight, Camera, DirectionalLight, FrameBufferProperties, Geom, GeomNode,
    GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    GraphicsEngine, GraphicsOutput, GraphicsPipe, GraphicsPipeSelection, LPoint3,
    NodePath, PerspectiveLens, PNMImage, Texture, Vec3, Vec4, WindowProperties, loadPrcFileData,
)
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'main.py'
source=MAIN.read_text()
tree=ast.parse(source)
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ASCIIMatterLab')
names={'_make_unit_bone_proto','_make_joint_proto','_make_skull_shell_proto','_style_bone_node','_reparent_preserve','_add_solid_bone','_build_internal_skeleton'}
methods={n.name:n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names}
assert methods.keys()==names
lines=source.splitlines()

def segment(fn):
    return textwrap.dedent('\n'.join(lines[fn.lineno-1:fn.end_lineno]))

class Args: safe_mode=False; no_skeleton=False
ARGS=Args()
SKELETON_CACHE=ROOT/'assets/cache/internal_skeleton.json'
def _checkpoint(*a,**k): pass
def _v3(value):
    if hasattr(value,'x'): return Vec3(float(value.x),float(value.y),float(value.z))
    return Vec3(float(value[0]),float(value[1]),float(value[2]))

ns=dict(globals())
for name,fn in methods.items():
    exec(segment(fn),ns)

class Probe:
    pass
Probe._make_unit_bone_proto=staticmethod(ns['_make_unit_bone_proto'])
Probe._make_joint_proto=staticmethod(ns['_make_joint_proto'])
Probe._make_skull_shell_proto=staticmethod(ns['_make_skull_shell_proto'])
Probe._style_bone_node=ns['_style_bone_node']
Probe._reparent_preserve=ns['_reparent_preserve']
Probe._add_solid_bone=ns['_add_solid_bone']
Probe._build_internal_skeleton=ns['_build_internal_skeleton']

loadPrcFileData('', 'load-display p3tinydisplay\nwindow-type offscreen\naudio-library-name null\nsync-video 0\n')
sel=GraphicsPipeSelection.getGlobalPtr(); sel.loadAuxModules(); pipe=sel.makeDefaultPipe()
assert pipe and pipe.getType().getName()=='TinyOffscreenGraphicsPipe'
engine=GraphicsEngine.getGlobalPtr(); fb=FrameBufferProperties(); fb.setRgbColor(True); fb.setDepthBits(24)
out=engine.makeOutput(pipe,'exact_pass14_probe',0,fb,WindowProperties.size(640,360),GraphicsPipe.BFRefuseWindow)
assert out is not None
out.setClearColorActive(True); out.setClearColor(Vec4(0,0,0,1)); out.setClearDepthActive(True); out.setActive(True)
tex=Texture('exact_pass14_probe'); out.addRenderTexture(tex,GraphicsOutput.RTMCopyRam,GraphicsOutput.RTPColor)
out.getDisplayRegion(0).setActive(True)
render=NodePath('render')
obj=Probe(); obj.render=render; obj.body_root=render.attachNewNode('ascii_body'); obj.skeleton_bones=[]; obj.skeleton_joints=[]; obj.skeleton_skull_parts=[]; obj.skeleton_segment_count=0; obj.skeleton_joint_count=0; obj.skeleton_skull_count=0; obj.rig_root=None; obj.rig_joints={}; obj.rig_rest_positions={}
obj._build_internal_skeleton()
cam_node=Camera('cam'); cam_node.setScene(render); lens=PerspectiveLens(); lens.setFov(42); lens.setNearFar(.05,20); cam_node.setLens(lens)
cam=render.attachNewNode(cam_node); cam.setPos(0,-4.0,1.0); cam.lookAt(LPoint3(0,0,0.95)); out.getDisplayRegion(0).setCamera(cam)
engine.renderFrame(); engine.syncFrame(); engine.renderFrame(); engine.syncFrame()
image=PNMImage(); screenshot_ok=bool(out.getScreenshot(image)); bright=0
if screenshot_ok:
    for y in range(image.getYSize()):
        for x in range(image.getXSize()):
            if max(image.getRed(x,y),image.getGreen(x,y),image.getBlue(x,y))>0.16: bright+=1
bounds=obj.skeleton_root.getTightBounds(); lo,hi=bounds if bounds else (None,None)
result={
 'source':'exact methods extracted from shipped main.py',
 'panda_pipe':pipe.getType().getName(),
 'segments':obj.skeleton_segment_count,
 'joints':obj.skeleton_joint_count,
 'skull_meshes':obj.skeleton_skull_count,
 'screenshot_memory_ok':screenshot_ok,
 'bright_pixels':bright,
 'visible_signal':bright>250,
 'bounds_min':[float(lo.x),float(lo.y),float(lo.z)] if lo else None,
 'bounds_max':[float(hi.x),float(hi.y),float(hi.z)] if hi else None,
}
(ROOT/'verification/panda_exact_skeleton_method_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
cache=json.loads(SKELETON_CACHE.read_text()); assert result['segments']==cache['metrics']['render_segment_count'] and result['joints']==cache['metrics']['joint_count'] and result['skull_meshes']==1 and result['visible_signal']
engine.removeWindow(out)
