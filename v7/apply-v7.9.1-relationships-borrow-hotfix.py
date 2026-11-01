from pathlib import Path
p=Path.cwd()/"src/ui/player_panel.rs"
if not p.exists(): raise SystemExit("v7.9.1: player_panel.rs missing")
t=p.read_text(encoding="utf-8")
old='''            ui.columns(2,|cols|{\n                let left=&mut cols[0];\n                left.set_min_width(520.0);'''
new='''            ui.columns(2,|cols|{\n                let (left_cols,right_cols)=cols.split_at_mut(1);\n                let left=&mut left_cols[0];\n                left.set_min_width(520.0);'''
if old not in t: raise SystemExit("v7.9.1: left column marker missing")
t=t.replace(old,new,1)
old='''                let right=&mut cols[1];\n                egui::Frame::group(right.style()).inner_margin(10.0).show(right,|ui|{'''
new='''                let right=&mut right_cols[0];\n                egui::Frame::group(right.style()).inner_margin(10.0).show(right,|ui|{'''
if old not in t: raise SystemExit("v7.9.1: right column marker missing")
t=t.replace(old,new,1)
p.write_text(t,encoding="utf-8")
print("Element v7.9.1 Relationships borrow hotfix applied.")
