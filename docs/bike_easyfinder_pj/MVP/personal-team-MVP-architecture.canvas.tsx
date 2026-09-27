import { useHostTheme } from "cursor/canvas";

const stages = [
  { title: "1. 候補取得", owner: "FastAPI", body: "位置・時間条件から距離圏内の候補を10〜20件返す。Apple ETAは呼ばない。" },
  { title: "2. ETA計算", owner: "iOS / MapKit", body: "MKDirections.calculateETAで表示予定候補だけを評価。端末内で短期キャッシュ。" },
  { title: "3. 最終順位", owner: "iOS Domain", body: "ETA、興味、visited、多様性を同じルール版で採点し最大5件へ絞る。" },
  { title: "4. ナビ委譲", owner: "Apple Maps", body: "MKMapItem.openInMapsで目的地を渡す。走行・帰着は追跡しない。" },
];

const changes = [
  ["Provider", "Server API", "MKDirections（端末）"],
  ["推薦API", "ETA込み最終5件", "粗い候補10〜20件"],
  ["最終ランキング", "FastAPI", "iOS Domain"],
  ["現在地送信", "APIへ送信", "丸める／送らない設計が可能"],
  ["キャッシュ", "サーバ共有", "端末内・短時間"],
  ["本番移行", "そのままServer API", "Provider境界で差し替え"],
];

export default function PersonalTeamMvpArchitecture() {
  const t = useHostTheme();
  const panel = { background: t.fill.tertiary, border: `1px solid ${t.stroke.secondary}`, borderRadius: 10 };
  return (
    <main style={{ background: t.bg.editor, color: t.text.primary, minHeight: "100vh", padding: 28, fontFamily: "system-ui", lineHeight: 1.5 }}>
      <header style={{ maxWidth: 980, margin: "0 auto 28px" }}>
        <div style={{ color: t.accent.primary, fontSize: 13, fontWeight: 700, letterSpacing: 1 }}>BIKE EASYFINDER · MVP ARCHITECTURE</div>
        <h1 style={{ fontSize: 24, margin: "8px 0" }}>Personal Team期間は、ETAをiOSへ移す</h1>
        <p style={{ color: t.text.secondary, maxWidth: 760, margin: 0 }}>Server APIの資格情報がない期間も、候補データはサーバ、Apple経路計算は端末、ナビはApple Mapsという責務分割でMVPを検証できる。</p>
      </header>

      <section style={{ maxWidth: 980, margin: "0 auto 30px" }}>
        <h2 style={{ fontSize: 17, marginBottom: 14 }}>推奨フロー</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 10 }}>
          {stages.map((s, i) => <div key={s.title} style={{ ...panel, padding: 15, position: "relative" }}>
            <div style={{ color: t.accent.primary, fontSize: 12, fontWeight: 700 }}>{s.owner}</div>
            <h3 style={{ fontSize: 15, margin: "5px 0 8px" }}>{s.title}</h3>
            <p style={{ color: t.text.secondary, fontSize: 13, margin: 0 }}>{s.body}</p>
            {i < stages.length - 1 && <span style={{ position: "absolute", right: -9, top: "45%", color: t.text.tertiary, zIndex: 2 }}>→</span>}
          </div>)}
        </div>
      </section>

      <section style={{ maxWidth: 980, margin: "0 auto", display: "grid", gridTemplateColumns: "1.35fr .65fr", gap: 18 }}>
        <div>
          <h2 style={{ fontSize: 17, marginBottom: 12 }}>基本設計から変わる境界</h2>
          <div style={{ ...panel, overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr 1.2fr", padding: "9px 13px", color: t.text.tertiary, fontSize: 12, borderBottom: `1px solid ${t.stroke.secondary}` }}><b>項目</b><b>現設計</b><b>Personal Team MVP</b></div>
            {changes.map((r, i) => <div key={r[0]} style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr 1.2fr", padding: "10px 13px", fontSize: 13, borderBottom: i < changes.length - 1 ? `1px solid ${t.stroke.tertiary}` : undefined }}><b>{r[0]}</b><span style={{ color: t.text.secondary }}>{r[1]}</span><span>{r[2]}</span></div>)}
          </div>
        </div>
        <aside>
          <h2 style={{ fontSize: 17, marginBottom: 12 }}>守る条件</h2>
          <div style={{ ...panel, padding: 16 }}>
            {[
              "MapKit要求は画面に出す候補だけ",
              "同時要求数を絞り、throttlingを処理",
              "高速回避はMKDirectionsの設定で検証",
              "ルール版をAPIとiOSで共有",
              "Server API復帰用Protocolを維持",
              "TestFlight・公開時はProgram登録",
            ].map(x => <div key={x} style={{ padding: "8px 0", borderBottom: `1px solid ${t.stroke.tertiary}`, fontSize: 13 }}>{x}</div>)}
          </div>
          <p style={{ color: t.text.tertiary, fontSize: 11, marginTop: 10 }}>根拠: Apple Developer Account / MapKit公式ドキュメント（2026-09-27確認）</p>
        </aside>
      </section>
    </main>
  );
}
