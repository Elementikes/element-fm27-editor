from pathlib import Path

p=Path.cwd()/"src/ui/player_data_hub.rs"
if not p.exists(): raise SystemExit("v7.4.1: player_data_hub.rs missing")
t=p.read_text(encoding="utf-8")

# fields_for_category yields Field values; readers take &Field.
t=t.replace("fields::read_field_u8(p,&p.raw,f)","fields::read_field_u8(p,&p.raw,&f)")

old='''            let Some(field)=schemas.fields_for_category(Entity::Player,category).iter().find(|f|f.label==metric) else{continue;};
            let vals:Vec<f32>=sampled.iter().filter_map(|p|fields::read_field_u8(*p,&p.raw,field).map(|v|v as f32)).filter(|v|(1.0..=20.0).contains(v)).collect();'''
new='''            let Some(field)=schemas.fields_for_category(Entity::Player,category).find(|f|f.label==metric) else{continue;};
            let vals:Vec<f32>=sampled.iter().filter_map(|p|fields::read_field_u8(*p,&p.raw,&field).map(|v|v as f32)).filter(|v|(1.0..=20.0).contains(v)).collect();'''
if old not in t:
    if new not in t: raise SystemExit("v7.4.1: metric iterator marker missing")
else:
    t=t.replace(old,new,1)

p.write_text(t,encoding="utf-8")
print("Element v7.4.1 Data Hub compile hotfix applied.")
