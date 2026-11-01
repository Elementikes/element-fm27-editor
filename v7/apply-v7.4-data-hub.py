from pathlib import Path

root = Path.cwd()


def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v7.4 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v7.4 marker missing: {label}")
    return text.replace(old,new,1)

# Register module.
p="src/ui/mod.rs"
t=rd(p)
if "pub mod player_data_hub;" not in t:
    t=one(t,"pub mod player_comparison;\n","pub mod player_comparison;\npub mod player_data_hub;\n","ui module")
wr(p,t)

(root/"src/ui/player_data_hub.rs").write_text(r'''use eframe::egui;

use crate::cache::{CachedPlayer, EntityCache};
use crate::fields::{self, Category, Entity, HasSubRecords, SubRecordId};
use crate::player::PlayerRecord;

impl HasSubRecords for CachedPlayer {
    fn sub_record(&self, _id: SubRecordId) -> Option<&[u8]> { None }
}

#[derive(Clone)]
struct Domain {
    label: &'static str,
    category: Category,
    score: f32,
    average: f32,
    percentile: f32,
    metrics: Vec<(&'static str, f32, f32, f32)>,
}

fn percentile(value:f32,values:&[f32])->f32{
    if values.is_empty(){return 0.0;}
    100.0*values.iter().filter(|v|**v<=value).count() as f32/values.len() as f32
}

fn player_category(
    schemas:&'static crate::fields::VersionedSchemas,
    p:&PlayerRecord,
    category:Category,
)->(f32,Vec<(&'static str,f32)>){
    let mut values=Vec::new();
    for f in schemas.fields_for_category(Entity::Player,category){
        if let Some(v)=fields::read_field_u8(p,&p.raw,f){
            if (1..=20).contains(&v){values.push((f.label,v as f32));}
        }
    }
    let avg=if values.is_empty(){0.0}else{values.iter().map(|x|x.1).sum::<f32>()/values.len() as f32};
    (avg/20.0*100.0,values)
}

fn cached_category(
    schemas:&'static crate::fields::VersionedSchemas,
    p:&CachedPlayer,
    category:Category,
)->Option<f32>{
    let mut total=0.0; let mut n=0usize;
    for f in schemas.fields_for_category(Entity::Player,category){
        if let Some(v)=fields::read_field_u8(p,&p.raw,f){
            if (1..=20).contains(&v){total+=v as f32;n+=1;}
        }
    }
    (n>0).then_some((total/n as f32)/20.0*100.0)
}

fn domains(
    schemas:&'static crate::fields::VersionedSchemas,
    player:&PlayerRecord,
    cache:Option<&EntityCache>,
)->Vec<Domain>{
    let definitions=[
        ("Technical",Category::Technical),
        ("Mental",Category::Mental),
        ("Physical",Category::Physical),
        ("Goalkeeping",Category::Goalkeeping),
        ("Set Pieces",Category::SetPieces),
    ];
    let cohort=cache.map(|c|c.players.as_slice()).unwrap_or(&[]);
    let cap=20_000usize; let step=(cohort.len()/cap).max(1);
    let sampled:Vec<&CachedPlayer>=cohort.iter().step_by(step).collect();
    definitions.into_iter().map(|(label,category)|{
        let (score,player_metrics)=player_category(schemas,player,category);
        let scores:Vec<f32>=sampled.iter().filter_map(|p|cached_category(schemas,p,category)).collect();
        let average=if scores.is_empty(){0.0}else{scores.iter().sum::<f32>()/scores.len() as f32};
        let mut metric_rows=Vec::new();
        for (metric,value) in player_metrics.into_iter().take(8){
            let Some(field)=schemas.fields_for_category(Entity::Player,category).iter().find(|f|f.label==metric) else{continue;};
            let vals:Vec<f32>=sampled.iter().filter_map(|p|fields::read_field_u8(*p,&p.raw,field).map(|v|v as f32)).filter(|v|(1.0..=20.0).contains(v)).collect();
            let avg=if vals.is_empty(){0.0}else{vals.iter().sum::<f32>()/vals.len() as f32};
            metric_rows.push((metric,value,avg,percentile(value,&vals)));
        }
        Domain{label,category,score,average,percentile:percentile(score,&scores),metrics:metric_rows}
    }).collect()
}

fn card(ui:&mut egui::Ui,title:&str,value:String,sub:String){
    egui::Frame::group(ui.style()).inner_margin(egui::Margin::same(8)).show(ui,|ui|{
        ui.set_min_width(118.0);
        ui.label(egui::RichText::new(title).size(8.5).strong().weak());
        ui.label(egui::RichText::new(value).size(20.0).strong());
        ui.label(egui::RichText::new(sub).size(8.0).weak());
    });
}

fn donut(ui:&mut egui::Ui,d:&Domain){
    let (rect,_)=ui.allocate_exact_size(egui::vec2(110.0,118.0),egui::Sense::hover());
    let p=ui.painter_at(rect); let center=egui::pos2(rect.center().x,rect.top()+46.0); let radius=30.0;
    p.circle_stroke(center,radius,egui::Stroke::new(8.0,egui::Color32::from_gray(48)));
    let sweep=d.score.clamp(0.0,100.0)/100.0*std::f32::consts::TAU;
    let mut pts=Vec::new();
    for i in 0..=48{let a=-std::f32::consts::FRAC_PI_2+sweep*i as f32/48.0;pts.push(center+egui::vec2(a.cos()*radius,a.sin()*radius));}
    if pts.len()>1{p.add(egui::Shape::line(pts,egui::Stroke::new(8.0,egui::Color32::from_rgb(116,145,255))));}
    p.text(center,egui::Align2::CENTER_CENTER,format!("{:.0}",d.score),egui::FontId::proportional(17.0),egui::Color32::WHITE);
    p.text(egui::pos2(rect.center().x,rect.top()+86.0),egui::Align2::CENTER_CENTER,d.label,egui::FontId::proportional(9.0),egui::Color32::LIGHT_GRAY);
    p.text(egui::pos2(rect.center().x,rect.top()+102.0),egui::Align2::CENTER_CENTER,format!("P{:.0}",d.percentile),egui::FontId::proportional(9.0),egui::Color32::from_rgb(116,145,255));
}

fn radar(ui:&mut egui::Ui,ds:&[Domain]){
    let axes:Vec<&Domain>=ds.iter().filter(|d|d.label!="Goalkeeping").collect();
    if axes.len()<3{return;}
    let (rect,_)=ui.allocate_exact_size(egui::vec2(330.0,250.0),egui::Sense::hover());
    let p=ui.painter_at(rect);let center=rect.center();let radius=92.0;let n=axes.len();
    for ring in [0.25f32,0.5,0.75,1.0]{
        let mut pts:Vec<egui::Pos2>=(0..n).map(|i|{let a=-std::f32::consts::FRAC_PI_2+i as f32/n as f32*std::f32::consts::TAU;center+egui::vec2(a.cos(),a.sin())*radius*ring}).collect();pts.push(pts[0]);
        p.add(egui::Shape::line(pts,egui::Stroke::new(1.0,egui::Color32::from_gray(62))));
    }
    let avg:Vec<egui::Pos2>=axes.iter().enumerate().map(|(i,d)|{let a=-std::f32::consts::FRAC_PI_2+i as f32/n as f32*std::f32::consts::TAU;center+egui::vec2(a.cos(),a.sin())*radius*(d.average/100.0).clamp(0.0,1.0)}).collect();
    let me:Vec<egui::Pos2>=axes.iter().enumerate().map(|(i,d)|{let a=-std::f32::consts::FRAC_PI_2+i as f32/n as f32*std::f32::consts::TAU;center+egui::vec2(a.cos(),a.sin())*radius*(d.score/100.0).clamp(0.0,1.0)}).collect();
    p.add(egui::Shape::convex_polygon(avg,egui::Color32::from_rgba_unmultiplied(105,135,180,30),egui::Stroke::new(1.5,egui::Color32::from_rgb(130,160,205))));
    p.add(egui::Shape::convex_polygon(me,egui::Color32::from_rgba_unmultiplied(116,145,255,42),egui::Stroke::new(2.0,egui::Color32::from_rgb(116,145,255))));
    for (i,d) in axes.iter().enumerate(){let a=-std::f32::consts::FRAC_PI_2+i as f32/n as f32*std::f32::consts::TAU;let pos=center+egui::vec2(a.cos(),a.sin())*(radius+24.0);p.text(pos,egui::Align2::CENTER_CENTER,d.label,egui::FontId::proportional(8.5),egui::Color32::LIGHT_GRAY);}
}

pub fn show(
    schemas:&'static crate::fields::VersionedSchemas,
    ui:&mut egui::Ui,
    player:&PlayerRecord,
    cache:Option<&EntityCache>,
){
    let ds=domains(schemas,player,cache);
    let cohort=cache.map(|c|c.players.len()).unwrap_or(0);
    let ca=player.field_u16("p_ca").unwrap_or(0) as f32; let pa=player.field_u16("p_pa").unwrap_or(0) as f32;
    let ca_vals:Vec<f32>=cache.map(|c|c.players.iter().map(|p|p.ca as f32).collect()).unwrap_or_default();
    let pa_vals:Vec<f32>=cache.map(|c|c.players.iter().map(|p|p.pa as f32).collect()).unwrap_or_default();
    let overall=if ds.is_empty(){0.0}else{ds.iter().filter(|d|d.label!="Goalkeeping").map(|d|d.score).sum::<f32>()/ds.iter().filter(|d|d.label!="Goalkeeping").count().max(1) as f32};

    ui.horizontal_wrapped(|ui|{ui.heading("Player Data Hub");ui.label(egui::RichText::new("ELEMENT v7.4 • LIVE ATTRIBUTE ANALYTICS").strong().color(egui::Color32::from_rgb(116,145,255)));});
    ui.add_space(6.0);
    ui.horizontal_wrapped(|ui|{
        card(ui,"CURRENT ABILITY",format!("{ca:.0}"),format!("P{:.0} vs database",percentile(ca,&ca_vals)));
        card(ui,"POTENTIAL ABILITY",format!("{pa:.0}"),format!("P{:.0} vs database",percentile(pa,&pa_vals)));
        card(ui,"COHORT",cohort.to_string(),"loaded players".into());
        card(ui,"PROFILE INDEX",format!("{overall:.0}"),"attributes /100".into());
    });
    ui.add_space(8.0);
    ui.horizontal(|ui|{
        ui.vertical(|ui|{ui.strong("PROFILE RADAR");ui.label(egui::RichText::new("Blue = player • grey-blue = database average").small().weak());radar(ui,&ds);});
        ui.separator();
        ui.vertical(|ui|{ui.strong("DOMAIN PERCENTILES");ui.horizontal_wrapped(|ui|{for d in &ds{donut(ui,d);}});});
    });
    ui.add_space(8.0);
    for d in &ds{
        egui::CollapsingHeader::new(format!("{} • {:.0}/100 • P{:.0}",d.label,d.score,d.percentile)).show(ui,|ui|{
            for (label,value,avg,pct) in &d.metrics{
                ui.horizontal(|ui|{ui.set_min_width(420.0);ui.label(*label);ui.label(format!("{value:.0}/20"));ui.label(format!("avg {avg:.1}"));ui.label(egui::RichText::new(format!("P{pct:.0}")).color(egui::Color32::from_rgb(116,145,255)));});
            }
        });
    }
    ui.add_space(10.0);
    egui::Frame::group(ui.style()).show(ui,|ui|{
        ui.strong("Native Match Performance");
        ui.label("Goals/90 • xG/90 • Assists/90 • xA/90 • Dribbles • Key Passes • Progressive Passes • Tackles • Interceptions • Aerials • Saves • xG Prevented");
        ui.label(egui::RichText::new("LOCKED: FM27 match-stat/history record chain is not certified yet. Element never fabricates performance numbers.").weak());
    });
}
''',encoding="utf-8")

# Player tab.
p="src/ui/player_panel.rs"
t=rd(p)
if "    DataHub,\n" not in t:
    t=one(t,"    TransferPower,\n}","    TransferPower,\n    DataHub,\n}","DataHub enum")
    t=one(t,'        ui.selectable_value(tab, PlayerTab::TransferPower, "Transfer Power");\n','        ui.selectable_value(tab, PlayerTab::TransferPower, "Transfer Power");\n        ui.selectable_value(tab, PlayerTab::DataHub, "Data Hub");\n',"DataHub button")
    arm='''        PlayerTab::TransferPower => {
            egui::ScrollArea::vertical()
                .id_salt("player_transfer_power")
                .show(ui, |ui| {
                    show_transfer_power(ui, player, entity_cache);
                });
        }
'''
    repl=arm+'''        PlayerTab::DataHub => {
            egui::ScrollArea::vertical()
                .id_salt("player_data_hub_v7")
                .show(ui, |ui| {
                    crate::ui::player_data_hub::show(schemas, ui, player, entity_cache);
                });
        }
'''
    t=one(t,arm,repl,"DataHub match arm")
wr(p,t)

print("Element v7.4 Data Hub applied.")
