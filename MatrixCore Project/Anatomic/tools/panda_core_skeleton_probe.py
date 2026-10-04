from pathlib import Path
import ast, json, math, textwrap
from panda3d.core import (
    AmbientLight, Camera, DirectionalLight, FrameBufferProperties, Geom, GeomNode,
    GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    GraphicsEngine, GraphicsOutput, GraphicsPipe, GraphicsPipeSelection, LPoint3,
    NodePath, PerspectiveLens, PNMImage, Texture, Vec3, Vec4, WindowProperties, loadPrcFileData,
)

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'assets/cache/internal_skeleton.json').read_text())
# Extract only the shipped cranium primitive for an engine-level geometry check;
# long-bone/joint generation below remains an independent implementation.
source=(ROOT/'main.py').read_text(); tree=ast.parse(source); lines=source.splitlines()
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ASCIIMatterLab')
fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_make_skull_shell_proto')
ns=dict(globals())
exec(textwrap.dedent('\n'.join(lines[fn.lineno-1:fn.end_lineno])),ns)
make_skull_shell=ns['_make_skull_shell_proto']
loadPrcFileData('', 'load-display p3tinydisplay\nwindow-type offscreen\naudio-library-name null\nsync-video 0\n')

def unit_bone(sides=8):
    fmt=GeomVertexFormat.getV3n3(); vd=GeomVertexData('probe_bone',fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vd,'vertex'); nw=GeomVertexWriter(vd,'normal'); prim=GeomTriangles(Geom.UHStatic)
    for i in range(sides):
        a=2*math.pi*i/sides; x,z=math.cos(a),math.sin(a)
        vw.addData3f(x,0,z); nw.addData3f(x,0,z)
        vw.addData3f(x,1,z); nw.addData3f(x,0,z)
    for i in range(sides):
        j=(i+1)%sides; a0,a1,b0,b1=2*i,2*j,2*i+1,2*j+1
        prim.addVertices(a0,a1,b1); prim.addVertices(a0,b1,b0)
    g=Geom(vd); g.addPrimitive(prim); gn=GeomNode('probe_bone'); gn.addGeom(g); return NodePath(gn)

def unit_joint():
    verts=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    faces=((4,0,2),(4,2,1),(4,1,3),(4,3,0),(5,2,0),(5,1,2),(5,3,1),(5,0,3))
    fmt=GeomVertexFormat.getV3n3(); vd=GeomVertexData('probe_joint',fmt,Geom.UHStatic)
    vw=GeomVertexWriter(vd,'vertex'); nw=GeomVertexWriter(vd,'normal')
    for v in verts: vw.addData3f(*v); nw.addData3f(*v)
    prim=GeomTriangles(Geom.UHStatic)
    for f in faces: prim.addVertices(*f)
    g=Geom(vd); g.addPrimitive(prim); gn=GeomNode('probe_joint'); gn.addGeom(g); return NodePath(gn)

sel=GraphicsPipeSelection.getGlobalPtr(); sel.loadAuxModules(); pipe=sel.makeDefaultPipe()
assert pipe and pipe.getType().getName()=='TinyOffscreenGraphicsPipe', pipe
engine=GraphicsEngine.getGlobalPtr(); fb=FrameBufferProperties(); fb.setRgbColor(True); fb.setDepthBits(24)
wp=WindowProperties.size(640,360)
out=engine.makeOutput(pipe,'pass14_probe',0,fb,wp,GraphicsPipe.BFRefuseWindow)
assert out is not None
out.setClearColorActive(True); out.setClearColor(Vec4(0,0,0,1)); out.setClearDepthActive(True)
tex=Texture('probe'); out.addRenderTexture(tex,GraphicsOutput.RTMCopyRam,GraphicsOutput.RTPColor)
out.setActive(True); out.getDisplayRegion(0).setActive(True)
render=NodePath('render'); skeleton=render.attachNewNode('solid_internal_skeleton')
proto=unit_bone(); joint_proto=unit_joint(); joints={k:Vec3(*v) for k,v in DATA['joints'].items()}
segments=[]
def add_seg(name,a,b,r):
    a=Vec3(*a) if not hasattr(a,'x') else a; b=Vec3(*b) if not hasattr(b,'x') else b
    d=b-a; L=d.length(); assert L>1e-6
    h=skeleton.attachNewNode('bone_'+name); proto.instanceTo(h); h.setPos(a); h.lookAt(b); h.setScale(float(r),float(L),float(r)); segments.append(h)
for bone in DATA['bones']: add_seg(bone['name'],joints[bone['a']],joints[bone['b']],bone['radius'])
for curve in DATA['curves']:
    pts=curve['points']
    for i,(a,b) in enumerate(zip(pts[:-1],pts[1:]),1): add_seg(f"{curve['name']}_{i}",a,b,curve['radius'])
skull_holder=skeleton.attachNewNode('skull_cranium_solid'); make_skull_shell(DATA['skull']).instanceTo(skull_holder)
for name,pos in joints.items():
    h=skeleton.attachNewNode('joint_'+name); joint_proto.instanceTo(h); h.setPos(pos); h.setScale(DATA['joint_radius'])
skeleton.setColor(*DATA['color'])
amb=AmbientLight('amb'); amb.setColor(Vec4(.24,.27,.29,1)); amb_np=render.attachNewNode(amb); skeleton.setLight(amb_np)
key=DirectionalLight('key'); key.setColor(Vec4(.88,.94,1,1)); key_np=render.attachNewNode(key); key_np.setHpr(-35,-55,0); skeleton.setLight(key_np)
cam_node=Camera('cam'); cam_node.setScene(render); lens=PerspectiveLens(); lens.setFov(42); lens.setNearFar(.05,20); cam_node.setLens(lens)
cam=render.attachNewNode(cam_node); cam.setPos(0,-4.0,1.00); cam.lookAt(LPoint3(0,0,0.95)); out.getDisplayRegion(0).setCamera(cam)
engine.renderFrame(); engine.syncFrame(); engine.renderFrame(); engine.syncFrame()
image=PNMImage(); screenshot_ok=bool(out.getScreenshot(image))
bright_pixels=0; nonzero=0
if screenshot_ok:
    for y in range(image.getYSize()):
        for x in range(image.getXSize()):
            r=image.getRed(x,y); g=image.getGreen(x,y); b=image.getBlue(x,y)
            if max(r,g,b)>0.16: bright_pixels+=1
            if max(r,g,b)>0.02: nonzero+=1
ram=bytes(tex.getRamImage())
rgb=b''
bounds=skeleton.getTightBounds(); lo,hi=bounds if bounds else (None,None)
result={
 'panda_pipe':pipe.getType().getName(), 'segments':len(segments), 'joints':len(joints), 'skull_meshes':1,
 'ram_bytes':len(ram), 'screenshot_ok':screenshot_ok, 'nonzero_pixels':nonzero, 'bright_pixels':bright_pixels,
 'visible_signal':bright_pixels>250,
 'bounds_min':[float(lo.x),float(lo.y),float(lo.z)] if lo else None,
 'bounds_max':[float(hi.x),float(hi.y),float(hi.z)] if hi else None,
}
(ROOT/'verification/panda_core_skeleton_probe.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert result['segments']==DATA['metrics']['render_segment_count'] and result['joints']==DATA['metrics']['joint_count'] and result['skull_meshes']==1 and result['visible_signal']
engine.removeWindow(out)
