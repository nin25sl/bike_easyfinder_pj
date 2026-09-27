import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  Pill,
  Row,
  Stack,
  Text,
  useHostTheme,
  useState,
} from "cursor/canvas";

type ScreenKey = "home" | "criteria" | "card" | "detail";

const screens: { key: ScreenKey; label: string; id: string }[] = [
  { key: "home", label: "ホーム", id: "S02" },
  { key: "criteria", label: "条件設定", id: "S03" },
  { key: "card", label: "提案カード", id: "S04" },
  { key: "detail", label: "詳細", id: "S05" },
];

function Phone({ screen }: { screen: ScreenKey }) {
  const theme = useHostTheme();
  const shell = {
    width: 330,
    minHeight: 630,
    border: `1px solid ${theme.stroke.primary}`,
    borderRadius: 28,
    background: theme.bg.editor,
    padding: 14,
  } as const;
  const inset = {
    padding: 14,
    borderRadius: 14,
    background: theme.fill.tertiary,
  } as const;
  const action = {
    padding: "13px 16px",
    borderRadius: 12,
    background: theme.accent.control,
    color: theme.text.onAccent,
    textAlign: "center" as const,
    fontWeight: 650,
  };

  return (
    <div style={shell}>
      <Stack gap={12}>
        <Row justify="space-between" align="center">
          <Text size="small" weight="semibold">9:41</Text>
          <Text size="small" tone="tertiary">Bike EasyFinder</Text>
        </Row>
        <Divider />
        {screen === "home" && (
          <>
            <Text size="small" tone="secondary">ホーム</Text>
            <div>
              <div style={{ fontSize: 23, fontWeight: 700, color: theme.text.primary }}>今日はどれくらい走る？</div>
              <Text tone="secondary">前回の条件ですぐに提案できます。</Text>
            </div>
            <div style={inset}>
              <Stack gap={10}>
                <Text weight="semibold">前回の条件</Text>
                <Row gap={6} wrap><Pill active>2時間</Pill><Pill active>海・景色</Pill><Pill>高速なし</Pill></Row>
                <Text size="small" tone="secondary">現在地は開始時に取得します</Text>
              </Stack>
            </div>
            <div style={action}>前回の条件で提案を受ける</div>
            <Button variant="secondary">条件を変更</Button>
            <Divider />
            <Row justify="space-between"><Text>興味あり</Text><Text weight="semibold">3件 ›</Text></Row>
            <Text size="small" tone="tertiary">設定とプライバシーは右上から</Text>
          </>
        )}
        {screen === "criteria" && (
          <>
            <Text size="small" tone="secondary">提案条件</Text>
            <div style={{ fontSize: 23, fontWeight: 700, color: theme.text.primary }}>どんな時間にする？</div>
            <Callout tone="success" title="現在地を取得しました">提案開始時にのみ利用します。</Callout>
            <Text weight="semibold">使える時間</Text>
            <Grid columns={3} gap={7}>
              {["1時間", "2時間", "3時間", "4時間", "半日", "1日"].map((v) => <Pill key={v} active={v === "2時間"}>{v}</Pill>)}
            </Grid>
            <Text weight="semibold">興味</Text>
            <Row gap={7} wrap><Pill active>海</Pill><Pill active>景色</Pill><Pill>カフェ</Pill><Pill>温泉</Pill><Pill>歴史</Pill><Pill>おまかせ</Pill></Row>
            <Text weight="semibold">高速道路</Text>
            <Row gap={7}><Pill active>使わない</Pill><Pill>使ってよい</Pill></Row>
            <div style={action}>この条件で提案を受ける</div>
          </>
        )}
        {screen === "card" && (
          <>
            <Row justify="space-between"><Text size="small" tone="secondary">あなたへの提案</Text><Text size="small">1 / 最大5件</Text></Row>
            <div style={{ height: 175, borderRadius: 14, background: theme.fill.secondary, display: "grid", placeItems: "center", color: theme.text.tertiary }}>
              Spot代表写真
            </div>
            <div>
              <div style={{ fontSize: 23, fontWeight: 700, color: theme.text.primary }}>桜井二見ヶ浦</div>
              <Row gap={6}><Pill size="sm">海</Pill><Pill size="sm">景色</Pill></Row>
            </div>
            <div style={inset}>
              <Text weight="bold">往復・滞在・余裕込み 1時間55分</Text>
              <Text size="small" tone="secondary">16:05ごろ帰着予想</Text>
            </div>
            <Text><Text weight="semibold">おすすめの理由：</Text>時間内で、海と景色の興味に合います。</Text>
            <Callout tone="warning">営業時間は現地情報をご確認ください。</Callout>
            <Button variant="secondary">詳細を見る</Button>
            <Row gap={6} wrap><Button variant="primary">興味あり</Button><Button variant="secondary">今回は違う</Button><Button variant="ghost">訪問済み</Button></Row>
          </>
        )}
        {screen === "detail" && (
          <>
            <Text size="small" tone="secondary">提案詳細</Text>
            <div style={{ fontSize: 23, fontWeight: 700, color: theme.text.primary }}>桜井二見ヶ浦</div>
            <Text tone="secondary">海沿いの景色と夫婦岩を楽しめる、短時間ツーリング向けの目的地。</Text>
            <div style={inset}>
              <Stack gap={7}>
                <Text weight="bold">合計 1時間55分</Text>
                <Row justify="space-between"><Text size="small">往路 35分</Text><Text size="small">滞在 30分</Text><Text size="small">復路 35分</Text><Text size="small">余裕 15分</Text></Row>
              </Stack>
            </div>
            <div style={{ height: 145, borderRadius: 14, border: `1px solid ${theme.stroke.secondary}`, display: "grid", placeItems: "center", color: theme.text.tertiary }}>
              MapKit 概要ルート
            </div>
            <Callout tone="warning" title="天気に注意">訪問時間帯は風が強い可能性があります。</Callout>
            <Row justify="space-between"><Text>情報の鮮度</Text><Text size="small" tone="secondary">7日前に確認</Text></Row>
            <div style={action}>ここに行く</div>
            <Text size="small" tone="tertiary">次に安全確認を表示してApple Mapsへ移動</Text>
          </>
        )}
      </Stack>
    </div>
  );
}

const decisions = [
  ["ブランド", "自然・信頼・落ち着き／深い青緑を推奨"],
  ["Spot写真", "採用を推奨。権利・出典・欠損時表示を要定義"],
  ["興味ラベル", "実データ後に6〜8個へ確定"],
  ["リアクション", "即時に次へ進み、Undoを約5秒表示"],
  ["天気注意", "詳細で表示し、ナビ確認でも要点を再掲"],
  ["分析同意", "任意で提示し、設定からいつでも変更可能"],
];

export default function BikeEasyFinderUIConcept() {
  const theme = useHostTheme();
  const [screen, setScreen] = useState<ScreenKey>("card");
  const selected = screens.find((item) => item.key === screen)!;

  return (
    <Stack gap={24} style={{ padding: 28, maxWidth: 1120, margin: "0 auto", color: theme.text.primary }}>
      <div>
        <Text size="small" tone="secondary">MVP UI DESIGN PROPOSAL · 2026-09-27</Text>
        <H1>迷わず、急かされず、安心して1件を選ぶ</H1>
        <Text tone="secondary">検索一覧ではなく、時間内の目的地を1件ずつ提案するiPhone体験。要件 S01〜S08のうち、中核4画面を視覚化しています。</Text>
      </div>

      <Grid columns="minmax(330px, 0.8fr) minmax(420px, 1.2fr)" gap={28} align="start">
        <Stack gap={12}>
          <Row gap={7} wrap>
            {screens.map((item) => <Pill key={item.key} active={screen === item.key} onClick={() => setScreen(item.key)}>{item.id} {item.label}</Pill>)}
          </Row>
          <Phone screen={screen} />
        </Stack>

        <Stack gap={18}>
          <div>
            <Text size="small" tone="tertiary">選択中</Text>
            <H2>{selected.id} {selected.label}</H2>
          </div>
          <Callout tone="info" title="UXの核">主要CTAは原則1つ。目的地名と合計時間を最上位にし、推薦理由と鮮度で判断を支えます。</Callout>
          <Card>
            <CardHeader>実装へ引き渡す共通ルール</CardHeader>
            <CardBody>
              <Stack gap={10}>
                <Text>・候補は常に1件を主表示し、一覧比較を主動線にしない</Text>
                <Text>・主CTAは下部Safe Area上、主要タップ領域は44pt以上</Text>
                <Text>・色だけで選択・警告・エラーを伝えない</Text>
                <Text>・Dynamic Type最大時は横並び操作を縦へ切り替える</Text>
                <Text>・リアクションは取り消し可能にし、同一Spotを同一セッションで再表示しない</Text>
              </Stack>
            </CardBody>
          </Card>
          <div>
            <H2>実装前に決める6項目</H2>
            <Stack gap={0}>
              {decisions.map(([title, body], index) => (
                <div key={title} style={{ padding: "12px 0", borderBottom: index < decisions.length - 1 ? `1px solid ${theme.stroke.tertiary}` : undefined }}>
                  <Row gap={12} align="start">
                    <div style={{ minWidth: 22, color: theme.accent.primary, fontWeight: 700 }}>{index + 1}</div>
                    <div><Text weight="semibold">{title}</Text><Text size="small" tone="secondary">{body}</Text></div>
                  </Row>
                </div>
              ))}
            </Stack>
          </div>
        </Stack>
      </Grid>
    </Stack>
  );
}

