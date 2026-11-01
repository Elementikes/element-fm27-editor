from pathlib import Path

root=Path.cwd()
p=root/'src/bridge/native_offer_probe.rs'
if not p.exists(): raise SystemExit('v8.4.3 missing native_offer_probe.rs')
t=p.read_text(encoding='utf-8')

old='''        let report=std::env::temp_dir().join("ElementFM27-native-offer-probe.txt");let _=std::fs::remove_file(&report);\n'''
new='''        let report=std::env::temp_dir().join("ElementFM27-native-offer-probe.txt");let _=std::fs::remove_file(&report);\n        let progress=std::env::temp_dir().join("ElementFM27-native-offer-probe-progress.txt");let _=std::fs::remove_file(&progress);\n'''
if old not in t: raise SystemExit('v8.4.3 report marker missing')
t=t.replace(old,new,1)

old='''        let started=Instant::now();while started.elapsed()<Duration::from_secs(5){if let Ok(s)=std::fs::read_to_string(&report){if !s.trim().is_empty(){return Ok(s);}}std::thread::sleep(Duration::from_millis(80));}\n        Err("helper loaded but no IL2CPP probe report arrived".into())\n'''
new='''        let started=Instant::now();while started.elapsed()<Duration::from_secs(15){if let Ok(s)=std::fs::read_to_string(&report){if !s.trim().is_empty(){return Ok(s);}}std::thread::sleep(Duration::from_millis(80));}\n        let checkpoint=std::fs::read_to_string(&progress).unwrap_or_else(|_|"<no checkpoint file written>".into());\n        let last=checkpoint.lines().last().unwrap_or("<empty checkpoint file>");\n        Err(format!("helper loaded but no final IL2CPP probe report arrived • last checkpoint: {last}"))\n'''
if old not in t: raise SystemExit('v8.4.3 timeout marker missing')
t=t.replace(old,new,1)

p.write_text(t,encoding='utf-8')
print('Element v8.4.3 Native Offer probe checkpoints applied.')
