from pathlib import Path

root=Path.cwd()
p=root/'src/ui/player_panel.rs'
if not p.exists(): raise SystemExit('v8.4.4 missing player_panel.rs')
t=p.read_text(encoding='utf-8')

t=t.replace('Native AI Offer Lab • v8.4','Native AI Offer Inspector • v8.4.4')

marker='''    ui.label(egui::RichText::new("Direct Settlement remains available above as fallback. Native Inbox SEND stays locked until this live signature is certified on your exact FM27 build.").small().weak());
'''
insert='''    let report_path=std::env::temp_dir().join("ElementFM27-native-offer-probe.txt");
    if let Ok(mut full_report)=std::fs::read_to_string(&report_path){
        if !full_report.trim().is_empty(){
            ui.add_space(6.0);
            egui::CollapsingHeader::new("📋 FULL NATIVE OFFER INSPECTOR REPORT")
                .default_open(true)
                .show(ui,|ui|{
                    ui.label(egui::RichText::new(format!("Report file: {}",report_path.display())).small().weak());
                    ui.add(egui::TextEdit::multiline(&mut full_report)
                        .desired_width(f32::INFINITY)
                        .desired_rows(16)
                        .font(egui::TextStyle::Monospace)
                        .interactive(false));
                });
        }
    }else{
        let progress_path=std::env::temp_dir().join("ElementFM27-native-offer-probe-progress.txt");
        if let Ok(progress)=std::fs::read_to_string(progress_path){
            if !progress.trim().is_empty(){ui.label(egui::RichText::new(format!("Inspector progress: {}",progress.replace('\\n'," → "))).small().weak());}
        }
    }
    ui.label(egui::RichText::new("Direct Settlement remains available above as fallback. Native Inbox SEND stays fail-closed until dispatcher ownership and every action argument are certified.").small().weak());
'''
if marker not in t: raise SystemExit('v8.4.4 native lab marker missing')
t=t.replace(marker,insert,1)
p.write_text(t,encoding='utf-8')
print('Element v8.4.4 Native Offer Inspector UI applied.')
