from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v7.9 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v7.9 marker missing: {label}")
    return text.replace(old,new,1)

p="src/ui/player_panel.rs"
t=rd(p)

if "    Relationships,\n" not in t:
    t=one(t,"    DataHub,\n}","    DataHub,\n    Relationships,\n    Status,\n    Languages,\n}","PlayerTab FMRTE surfaces")

    data_arm='''        PlayerTab::DataHub => {
            egui::ScrollArea::vertical()
                .id_salt("player_data_hub_v7")
                .show(ui, |ui| {
                    crate::ui::player_data_hub::show(schemas, ui, player, entity_cache);
                });
        }
'''
    new_arms=data_arm+'''        PlayerTab::Relationships => {
            egui::ScrollArea::vertical()
                .id_salt("player_relationships_v79")
                .show(ui, |ui| show_relationships_panel(schemas, ui, player, &mut edits));
        }
        PlayerTab::Status => {
            egui::ScrollArea::vertical()
                .id_salt("player_status_v79")
                .show(ui, |ui| show_player_status(schemas, ui, player, addr, &mut edits));
        }
        PlayerTab::Languages => {
            egui::ScrollArea::vertical()
                .id_salt("player_languages_v79")
                .show(ui, |ui| show_languages_panel(ui, player));
        }
'''
    t=one(t,data_arm,new_arms,"PlayerTab FMRTE match arms")

if "fn show_relationships_panel(" not in t:
    marker="// ---------------------------------------------------------------------------\n// Overview\n// ---------------------------------------------------------------------------\n"
    functions=r'''fn show_languages_panel(ui: &mut egui::Ui, player: &PlayerRecord) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Languages");
        ui.label(egui::RichText::new("ELEMENT v7.9 • LIVE READ").strong().color(egui::Color32::from_rgb(96,178,255)));
    });
    ui.add_space(6.0);
    egui::Frame::group(ui.style()).inner_margin(10.0).show(ui, |ui| {
        match player.languages.as_ref() {
            Some(items) if items.is_empty() => { ui.label("No language records loaded."); }
            Some(items) => {
                egui::Grid::new(("element_languages_grid",player.addr)).striped(true).spacing([24.0,6.0]).show(ui,|ui|{
                    ui.strong("Language"); ui.strong("Proficiency"); ui.end_row();
                    for lang in items { ui.label(&lang.name); ui.label(lang.level); ui.end_row(); }
                });
            }
            None => { ui.label("Language chain unavailable for this record/build."); }
        }
    });
    ui.add_space(8.0);
    ui.add_enabled(false,egui::Button::new("＋ ADD LANGUAGE • MAPPING"))
        .on_disabled_hover_text("Reading is live. Insert/remove semantics remain locked until vector allocation is independently certified.");
}

fn show_relationships_panel(
    schemas: &'static fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Relationships");
        ui.label(egui::RichText::new("ELEMENT v7.9 • EXISTING RECORDS LIVE").strong().color(egui::Color32::from_rgb(96,178,255)));
    });
    ui.label(egui::RichText::new("FMRTE-style list + inspector. Element only edits the strength byte of an existing mapped club relationship; record insertion/removal stays locked.").weak());
    ui.add_space(6.0);

    let Some(layout)=schemas.player_lists else { ui.label("Relationship layout unavailable."); return; };
    let selected_id=egui::Id::new(("element_relationship_selected",player.addr));
    let mut selected=ui.ctx().data(|d|d.get_temp::<u64>(selected_id));

    match &mut player.relations {
        ListState::Unmapped => { ui.label("Relationships are not mapped for this build."); }
        ListState::Unreadable => { ui.label("Relationship vector could not be read."); }
        ListState::Items(items) => {
            if selected.is_none() { selected=items.first().map(|r|r.addr); }
            ui.columns(2,|cols|{
                let left=&mut cols[0];
                left.set_min_width(520.0);
                egui::Frame::group(left.style()).inner_margin(8.0).show(left,|ui|{
                    ui.horizontal(|ui|{ui.strong("Relationships");ui.with_layout(egui::Layout::right_to_left(egui::Align::Center),|ui|{
                        ui.add_enabled(false,egui::Button::new("−"));
                        ui.add_enabled(false,egui::Button::new("＋"));
                    });});
                    ui.separator();
                    egui::Grid::new(("element_relationship_grid",player.addr)).striped(true).min_col_width(80.0).spacing([12.0,5.0]).show(ui,|ui|{
                        for h in ["Type","Name","Value","Reason"] { ui.label(egui::RichText::new(h).strong()); }
                        ui.end_row();
                        for r in items.iter() {
                            let ty=if r.kind==layout.kind_club && r.relation_type==layout.type_favoured_club {"Likes Team"}
                                else if r.kind==layout.kind_nation && r.relation_type==layout.type_other_nationality {"Other Nationality"}
                                else {"Relationship"};
                            let reason=layout.favoured_club_reasons.iter().find(|(code,_)|*code==r.reason).map(|(_,name)|*name).unwrap_or("—");
                            let resp=ui.selectable_label(selected==Some(r.addr),ty);
                            if resp.clicked(){selected=Some(r.addr);ui.ctx().data_mut(|d|d.insert_temp(selected_id,r.addr));}
                            ui.label(&r.name);
                            ui.label(if ty=="Likes Team"{r.strength.to_string()}else{"—".into()});
                            ui.label(reason);
                            ui.end_row();
                        }
                    });
                });

                let right=&mut cols[1];
                egui::Frame::group(right.style()).inner_margin(10.0).show(right,|ui|{
                    ui.strong("Relationship");ui.separator();
                    let Some(addr)=selected else {ui.label("Select a relationship.");return;};
                    let Some(r)=items.iter_mut().find(|r|r.addr==addr) else {ui.label("Relationship no longer loaded.");return;};
                    let club_relation=r.kind==layout.kind_club && r.relation_type==layout.type_favoured_club;
                    let ty=if club_relation{"Likes Team"}else if r.kind==layout.kind_nation && r.relation_type==layout.type_other_nationality{"Other Nationality"}else{"Relationship"};
                    crate::ui::field_widget::info_label(ui,"Type",ty);
                    crate::ui::field_widget::info_label(ui,if club_relation{"Club"}else{"Nation"},&r.name);
                    if club_relation {
                        let mut value=r.strength;
                        ui.horizontal(|ui|{
                            ui.label("Value");
                            let changed=ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Slider::new(&mut value,0..=100).show_value(true)).changed();
                            if changed {
                                let old=r.strength;
                                r.strength=value;
                                edits.push(FieldEdit{
                                    addr:r.addr+layout.relation_strength as u64,
                                    old_raw:vec![old],new_raw:vec![value],
                                    description:format!("Relationship {} strength: {} → {}",r.name,old,value),
                                    presentation:Some(crate::edit_history::EditPresentation::new(format!("Relationship: {}",r.name),old,value)),
                                });
                            }
                        });
                        let reason=layout.favoured_club_reasons.iter().find(|(code,_)|*code==r.reason).map(|(_,name)|*name).unwrap_or("Unknown");
                        crate::ui::field_widget::info_label(ui,"Reason",reason);
                    } else {
                        crate::ui::field_widget::info_label(ui,"Nationality info","Existing nationality relation");
                    }
                });
            });
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui|{
                ui.add_enabled(false,egui::Button::new("＋ ADD RELATIONSHIP • MAPPING"));
                ui.add_enabled(false,egui::Button::new("REMOVE SELECTED • MAPPING"));
                ui.label(egui::RichText::new("Vector allocation/deallocation remains locked; existing value edits are guarded and undoable.").small().weak());
            });
        }
    }
}

'''
    t=one(t,marker,functions+marker,"FMRTE player surfaces functions")
wr(p,t)

# Context sidebar: route the existing FMRTE labels to the new dedicated pages.
p="src/app.rs"
t=rd(p)
t=t.replace('pnav!("✚  Injury", player_panel::PlayerTab::Overview);','pnav!("✚  Injury", player_panel::PlayerTab::Status);',1)
t=t.replace('pnav!("⊘  Unavailability", player_panel::PlayerTab::Overview);','pnav!("⊘  Unavailability", player_panel::PlayerTab::Status);',1)
t=t.replace('pnav!("♟  Relationships", player_panel::PlayerTab::Overview);','pnav!("♟  Relationships", player_panel::PlayerTab::Relationships);',1)
t=t.replace('pnav!("A  Languages", player_panel::PlayerTab::Overview);','pnav!("A  Languages", player_panel::PlayerTab::Languages);',1)
wr(p,t)

print("Element v7.9 FMRTE-style Player surfaces applied.")
