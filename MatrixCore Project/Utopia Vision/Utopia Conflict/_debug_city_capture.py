
import sys, json, os
sys.argv = ["main.py", "--no-audio"]
import main
app = main.EtchlineGame()
point = app.campaign_points[0]
app.player_pos = main.Vec3(point["pos"].x, point["pos"].y, app.game_cfg.player_height)
app.camera.setPos(app.player_pos)
snapshots = []
for i in range(220):
    app.update_campaign_objectives(0.033)
    app.update_spawn_director(0.033)
    app.update_enemies(0.033)
    if i in [0, 1, 10, 40, 80, 120, 180, 219]:
        snapshots.append({
            "i": i,
            "progress": point.get("progress"),
            "wave_triggered": point.get("wave_triggered"),
            "pending": len(getattr(app, "pending_enemy_spawns", [])),
            "enemies": len(getattr(app, "enemies", [])),
            "captured": point.get("captured"),
            "banner": getattr(app, "objective_banner", ""),
        })
enemy_positions = []
for e in getattr(app, "enemies", [])[:8]:
    try:
        p = e.root.getPos(app.render)
        enemy_positions.append([p.x, p.y, p.z])
    except Exception as exc:
        enemy_positions.append(["ERR", str(exc)])
print(json.dumps({
    "campaign_count": len(app.campaign_points),
    "first_pos": [point["pos"].x, point["pos"].y, point["pos"].z],
    "player_pos": [app.player_pos.x, app.player_pos.y, app.player_pos.z],
    "snapshots": snapshots,
    "pending": [{"pos":[p["pos"].x,p["pos"].y,p["pos"].z],"timer":p["timer"],"source":p.get("source")} for p in getattr(app,"pending_enemy_spawns",[])],
    "enemy_positions": enemy_positions,
}, indent=2))
app.userExit()
