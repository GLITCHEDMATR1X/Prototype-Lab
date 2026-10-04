from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/"assets/cache/internal_skeleton.json").read_text())
parents=data["rig_parent"]; joints=data["joints"]
def descendants(root):
    out=set(); frontier=[root]
    while frontier:
        cur=frontier.pop()
        for child,p in parents.items():
            if p==cur and child not in out:
                out.add(child); frontier.append(child)
    return out
left=descendants("left_elbow"); right=descendants("right_elbow")
left_expected={"left_wrist","left_hand"}|{f"left_{f}_{part}" for f in ("thumb","index","middle","ring","pinky") for part in ("root","mid","tip")}
right_expected={"right_wrist","right_hand"}|{f"right_{f}_{part}" for f in ("thumb","index","middle","ring","pinky") for part in ("root","mid","tip")}
forbidden={"pelvis","spine_low","spine_mid","spine_high","neck","head_base","left_shoulder","right_shoulder","left_hip","right_hip"}
checks={
 "left_descendants_complete":left_expected<=left,
 "right_descendants_complete":right_expected<=right,
 "left_no_body_parent":not (left & forbidden),
 "right_no_body_parent":not (right & forbidden),
 "arms_disjoint":not (left & right),
 "ten_fingers":len(data.get("finger_names",[]))==5 and sum(1 for j in joints if j.endswith("_tip") and any(f in j for f in data.get("finger_names",[])))==10,
}
result={"pass":all(checks.values()),"checks":checks,"left_descendant_count":len(left),"right_descendant_count":len(right),"joint_count":len(joints)}
(ROOT/"verification/arm_articulation_math.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
raise SystemExit(0 if result["pass"] else 1)
