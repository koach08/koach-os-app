import type { Phase, KajabiInfo, InjuryPrevention } from "@/types/training";

export const PHASES: Phase[] = [
  {
    id: 0,
    title: "Phase 0: 身体リセット",
    subtitle: "減量 + 血管改善 + 腰痛予防",
    weeks: "Week 1–6",
    color: "#ff4444",
    goal: "78kg→73kg / 腰痛ゼロ / 基礎体力UP",
    sections: [
      {
        name: "🌅 毎朝 5分（起床後）",
        exercises: [
          { name: "キャットカウ", reps: "10回", video: "https://www.youtube.com/watch?v=kqnua4rHVVA", note: "腰の可動域回復。吸って背中反る→吐いて丸める" },
          { name: "デッドバグ", reps: "10回/片側", video: "https://www.youtube.com/watch?v=I5xbRFkElOA", note: "腰痛予防の最重要エクササイズ。腰を床に押し付けたまま" },
          { name: "ヒップサークル（四つ這い）", reps: "10回/片側", video: "https://www.youtube.com/watch?v=bPIwlGBMVeE", note: "股関節の可動域回復" },
          { name: "手首サークル", reps: "各方向20回", video: "https://www.youtube.com/watch?v=mSZWSQSSEjE", note: "パワームーブ準備。手首は最も壊れやすい" },
        ],
      },
      {
        name: "🏢 昼休み/仕事合間 5分",
        exercises: [
          { name: "壁腕立て伏せ", reps: "15回", video: "https://www.youtube.com/watch?v=1Ls-w0FDCRs", note: "肩・手首の準備運動として" },
          { name: "椅子スクワット", reps: "15回", video: "https://www.youtube.com/watch?v=1Lg4pkmRNA4", note: "椅子に座る→立つをゆっくり繰り返す" },
          { name: "ストラドルストレッチ", reps: "30秒", video: "https://www.youtube.com/watch?v=3HVsDnBPIbk", note: "ウィンドミルの開脚に必須" },
          { name: "パイクストレッチ", reps: "30秒", video: "https://www.youtube.com/watch?v=FI95FgKBfEY", note: "ハムストリング柔軟性" },
        ],
      },
      {
        name: "🌙 夜 10分（寝る前）",
        exercises: [
          { name: "プランク", reps: "30秒×3", video: "https://www.youtube.com/watch?v=ASdvN_XEl_c", note: "肘つきでOK。腰が落ちないように" },
          { name: "サイドプランク", reps: "20秒/片側×2", video: "https://www.youtube.com/watch?v=K2VljzCC16g", note: "ウィンドミル時の横方向の安定に" },
          { name: "グルートブリッジ", reps: "15回", video: "https://www.youtube.com/watch?v=OUgsJ8-Vi0E", note: "腰痛予防+お尻の活性化" },
          { name: "90/90ヒップストレッチ", reps: "30秒/片側", video: "https://www.youtube.com/watch?v=rVWhAkkB1Gw", note: "股関節の内旋・外旋。フロアワークに必須" },
          { name: "手首ストレッチ（前後）", reps: "各30秒", video: "https://www.youtube.com/watch?v=mSZWSQSSEjE", note: "倒立・パワームーブの手首保護" },
          { name: "Lシット（椅子使用）", reps: "10秒×3", video: "https://www.youtube.com/watch?v=IUZJoSP66HI", note: "体幹圧縮力。フレアに直結" },
        ],
      },
      {
        name: "💪 週2回：有酸素+体幹",
        exercises: [
          { name: "ウォーキング/軽いジョグ", reps: "30分", video: null, note: "心拍120-140。血管年齢改善に最も効果的" },
          { name: "バーピー", reps: "5回×5セット", video: "https://www.youtube.com/watch?v=TU8QYVW0gDU", note: "全身運動+心拍UP。REST 60秒" },
          { name: "マウンテンクライマー", reps: "20秒×4", video: "https://www.youtube.com/watch?v=nmwgirgXLYM", note: "体幹+有酸素" },
          { name: "ホロウボディホールド", reps: "20秒×3", video: "https://www.youtube.com/watch?v=LlDNef_Ztsc", note: "体操選手の基本。バク転のタック姿勢に直結" },
          { name: "スーパーマンホールド", reps: "20秒×3", video: "https://www.youtube.com/watch?v=cc6DKRVO7Kc", note: "背筋強化。ブリッジへの準備" },
        ],
      },
      {
        name: "🏋️ 週1-2回：筋力ベース",
        exercises: [
          { name: "腕立て伏せ", reps: "できる回数×3", video: "https://www.youtube.com/watch?v=IODxDxX7oi4", note: "フォーム重視。胸が床に触れるまで" },
          { name: "パイクプッシュアップ", reps: "8回×3", video: "https://www.youtube.com/watch?v=sposDXWEB0A", note: "倒立プッシュアップの準備段階" },
          { name: "ディップス（椅子使用）", reps: "8回×3", video: "https://www.youtube.com/watch?v=HCijjmaGGKo", note: "三頭筋+肩。倒立の支持力" },
          { name: "スクワット", reps: "15回×3", video: "https://www.youtube.com/watch?v=aclHkVaku9U", note: "バク転の跳躍力の土台" },
          { name: "ランジ", reps: "10回/片側×3", video: "https://www.youtube.com/watch?v=QOVaHwm-Q6U", note: "片脚の安定性" },
          { name: "ハンギングレッグレイズ", reps: "8回×3", video: "https://www.youtube.com/watch?v=Pr1ieGZ5atk", note: "鉄棒で。バク転のタックに必要な腹筋力" },
        ],
      },
      {
        name: "🔄 月2回：アクロバット練習（継続）",
        exercises: [
          { name: "壁倒立→壁なし挑戦", reps: "10分", video: "https://www.youtube.com/watch?v=OYehg2ruMN0", note: "全ての逆さ系の基本" },
          { name: "バックロール→タックジャンプ連結", reps: "10分", video: "https://www.youtube.com/watch?v=a4MXEznMaqs", note: "後方回転への恐怖克服の第一歩" },
          { name: "フリーズ復習（チェア・ベビー・エルボー）", reps: "10分", video: "https://www.youtube.com/watch?v=B0oSllXLEgQ", note: "ブレイキンの基本ポジション" },
          { name: "6ステップ・フットワーク復習", reps: "10分", video: "https://www.youtube.com/watch?v=0Xro2vnKyGY", note: "ブレイキンの基礎中の基礎" },
        ],
      },
    ],
    milestones: ["体重73kg以下", "壁倒立30秒", "プランク60秒", "開脚120度以上", "腰痛なしで前転・後転"],
  },
  {
    id: 1,
    title: "Phase 1: ファンデーション復活",
    subtitle: "ブレイキン復活 + アクロバット準備",
    weeks: "Week 7–14",
    color: "#ff9900",
    goal: "ウィンドミル・スワイプス復活 / 壁なし倒立20秒 / マカコ習得",
    sections: [
      {
        name: "🌅 毎朝 7分",
        exercises: [
          { name: "キャットカウ", reps: "10回", video: "https://www.youtube.com/watch?v=kqnua4rHVVA", note: "継続" },
          { name: "デッドバグ", reps: "12回/片側", video: "https://www.youtube.com/watch?v=I5xbRFkElOA", note: "回数UP" },
          { name: "手首プッシュアップ", reps: "10回", video: "https://www.youtube.com/watch?v=8lDC4Ri9zAQ", note: "手首を曲げた状態から押す。手首強化" },
          { name: "肩CARs", reps: "5回/片側", video: "https://www.youtube.com/watch?v=PxMKCsGSbNs", note: "Controlled Articular Rotations。肩の全可動域" },
        ],
      },
      {
        name: "🏢 昼 7分",
        exercises: [
          { name: "パイクプッシュアップ", reps: "10回", video: "https://www.youtube.com/watch?v=sposDXWEB0A", note: "倒立力UP" },
          { name: "ピストルスクワット（椅子補助）", reps: "5回/片側", video: "https://www.youtube.com/watch?v=vq5-vdgJc0I", note: "片脚の爆発力。バク転に" },
          { name: "Lシット", reps: "15秒×3", video: "https://www.youtube.com/watch?v=IUZJoSP66HI", note: "時間延長" },
          { name: "パンケーキストレッチ", reps: "45秒", video: "https://www.youtube.com/watch?v=3Ymjw7TSzrE", note: "開脚前屈。ウィンドミルの開脚改善" },
        ],
      },
      {
        name: "🌙 夜 10分",
        exercises: [
          { name: "ホロウボディ", reps: "30秒×3", video: "https://www.youtube.com/watch?v=LlDNef_Ztsc", note: "時間延長" },
          { name: "フルブリッジ", reps: "10回", video: "https://www.youtube.com/watch?v=VjSP0jPjyXY", note: "肩の柔軟性+背中のアーチ。バク転に必須" },
          { name: "90/90ヒップストレッチ", reps: "45秒/片側", video: "https://www.youtube.com/watch?v=rVWhAkkB1Gw", note: "時間延長" },
          { name: "壁倒立→壁なし", reps: "20秒×3-5", video: "https://www.youtube.com/watch?v=OYehg2ruMN0", note: "壁なしへ移行" },
        ],
      },
      {
        name: "🔥 ブレイキン復活（週1回目標）",
        exercises: [
          { name: "トップロック", reps: "10分", video: "https://www.youtube.com/watch?v=Blz_07K0oSA", note: "音楽かけて。インディアンステップ、クロスステップ" },
          { name: "6ステップ・3ステップ", reps: "10分", video: "https://www.youtube.com/watch?v=0Xro2vnKyGY", note: "フットワークの基本" },
          { name: "バックスピン", reps: "10分", video: "https://www.youtube.com/watch?v=tRuVVblKBQQ", note: "ウィンドミルの前提スキル" },
          { name: "ウィンドミル復活ドリル", reps: "15分", video: "https://www.youtube.com/watch?v=vy9FFD-YeMU", note: "BBoy Dojo Focus式。タートルフリーズから" },
          { name: "スワイプス復活", reps: "10分", video: "https://www.youtube.com/watch?v=D8RfLZ--mf0", note: "腕のスイング→コア回転→脚のキック" },
        ],
      },
      {
        name: "🤸 アクロバット基礎（月2回）",
        exercises: [
          { name: "後転（完璧にする）", reps: "10分", video: "https://www.youtube.com/watch?v=a4MXEznMaqs", note: "首を守る。手を耳の横に" },
          { name: "タックジャンプ", reps: "10回×3", video: "https://www.youtube.com/watch?v=q3BilWL1fCE", note: "膝を胸まで引く。バク転のタック練習" },
          { name: "マカコ練習", reps: "15分", video: "https://www.youtube.com/watch?v=bM5bYOH6j6c", note: "後方に手をついて回る。バク転への段階的プログレッション" },
          { name: "バタフライキック基礎", reps: "10分", video: "https://www.youtube.com/watch?v=W7A8xN_bJPg", note: "B-Twistの前提技。水平回転の感覚" },
        ],
      },
      {
        name: "🏋️ 筋力（週1-2回）",
        exercises: [
          { name: "倒立プッシュアップ（壁あり）", reps: "5回×3", video: "https://www.youtube.com/watch?v=VQalY1JWe44", note: "肩の爆発的な押す力" },
          { name: "プライオプッシュアップ", reps: "5回×3", video: "https://www.youtube.com/watch?v=U1_WLCeDJbE", note: "手が浮くレベル。パワーの瞬発力" },
          { name: "ジャンプスクワット", reps: "10回×3", video: "https://www.youtube.com/watch?v=A-cFYGvaYpM", note: "バク転の跳躍力" },
          { name: "タックアップ（V字）", reps: "10回×3", video: "https://www.youtube.com/watch?v=rBBVUVAOdEY", note: "仰向けからV字起き上がり。体幹圧縮" },
        ],
      },
    ],
    milestones: ["ウィンドミル3回連続", "スワイプス3回", "壁なし倒立20秒", "フルブリッジ（肩開く）", "マカコ自力", "タックジャンプ膝が胸に触れる"],
  },
  {
    id: 2,
    title: "Phase 2: 技の習得",
    subtitle: "バク転 + B-Twist + パワームーブ強化",
    weeks: "Week 15–26",
    color: "#00cc66",
    goal: "バク転単発 / B-Twist着地 / フレア復活 / ヘイロー復活",
    sections: [
      {
        name: "🌅 毎朝 5分（メンテナンス）",
        exercises: [
          { name: "モビリティフロー", reps: "3分", video: "https://www.youtube.com/watch?v=SsT_go-yZ7c", note: "肩→背骨→股関節を流れるように" },
          { name: "手首プレハブ", reps: "2分", video: "https://www.youtube.com/watch?v=mSZWSQSSEjE", note: "サークル→プッシュ→ロード" },
        ],
      },
      {
        name: "🏢 昼 5分",
        exercises: [
          { name: "倒立", reps: "30秒×2", video: "https://www.youtube.com/watch?v=OYehg2ruMN0", note: "壁なしで維持" },
          { name: "Lシット", reps: "20秒×2", video: "https://www.youtube.com/watch?v=IUZJoSP66HI", note: "スキル維持" },
        ],
      },
      {
        name: "🤸 バク転プログレッション（マット上・スポッター推奨）",
        exercises: [
          { name: "セット練習", reps: "10回", video: "https://www.youtube.com/watch?v=LJPCNNPezn8", note: "ジャンプ→アームスイング→フルエクステンション" },
          { name: "マカコ→バックハンドスプリング移行", reps: "5回", video: "https://www.youtube.com/watch?v=bM5bYOH6j6c", note: "マカコの延長で手を遠くに着く" },
          { name: "坂利用バク転ドリル", reps: "5回", video: "https://www.youtube.com/watch?v=EjYwTTFOpjw", note: "傾斜マットで回転の感覚を掴む" },
          { name: "スポッター付きバク転", reps: "5-10回", video: "https://www.youtube.com/watch?v=sMKCdKP4a2Q", note: "Tシャツドリル:スポッターがTシャツを掴んでサポート" },
          { name: "自力バク転→連続", reps: "挑戦", video: "https://www.youtube.com/watch?v=LJPCNNPezn8", note: "恐怖克服がカギ。Set-Jump-Tuck-Land" },
        ],
      },
      {
        name: "🌀 B-Twist プログレッション",
        exercises: [
          { name: "バタフライキック（高さ・水平意識）", reps: "10回", video: "https://www.youtube.com/watch?v=W7A8xN_bJPg", note: "後ろ脚を高く上げて体を水平に" },
          { name: "ツナミ（ステップオーバーフックキック）", reps: "10回", video: "https://www.youtube.com/watch?v=vqI2kI6LFxA", note: "B-Twistの最重要プログレッション" },
          { name: "ツナミ→ノーキック→ハイパー", reps: "10回", video: "https://www.youtube.com/watch?v=vqI2kI6LFxA", note: "蹴り脚曲げて360°回転。TrixNut式" },
          { name: "ディッピング追加", reps: "10回", video: "https://www.youtube.com/watch?v=JfIiJfBJJqw", note: "上体を倒して水平に近づける" },
          { name: "B-Twist本番", reps: "5-10回", video: "https://www.youtube.com/watch?v=JfIiJfBJJqw", note: "芝生orマット上。腕を広げてからコイル" },
        ],
      },
      {
        name: "💨 パワームーブ強化",
        exercises: [
          { name: "ウィンドミル 5回連続以上", reps: "15分", video: "https://www.youtube.com/watch?v=vy9FFD-YeMU", note: "脚ストレート・ヒップ高く" },
          { name: "ベビーミル復活", reps: "10分", video: "https://www.youtube.com/watch?v=qLLwCFTl5sM", note: "タートル→ベビーミル移行" },
          { name: "ヘイロー復活", reps: "10分", video: "https://www.youtube.com/watch?v=5rRR-1yh5P8", note: "ベビーフリーズ→ヘッドスライド→回転" },
          { name: "トーマスフレア復活", reps: "15分", video: "https://www.youtube.com/watch?v=mj5pKjKBSIA", note: "Lシット→フレア入り。まず1-2回から" },
          { name: "Air Flare基礎（HDコース）", reps: "15分", video: null, note: "Handstand Daddy Course Level 1続き（Kajabi）" },
        ],
      },
    ],
    milestones: ["バク転マット上で自力", "B-Twist着地", "ウィンドミル→ベビーミル移行", "ヘイロー2回", "フレア3回", "30秒セット×3ラウンド"],
  },
  {
    id: 3,
    title: "Phase 3: バトルレディ",
    subtitle: "バク宙 + Air Flare + 実戦",
    weeks: "Week 27–36+",
    color: "#9933ff",
    goal: "バク宙 / Air Flare 1回 / バトル参戦",
    sections: [
      {
        name: "🤸 バク宙プログレッション",
        exercises: [
          { name: "完璧なタックジャンプ", reps: "10回", video: "https://www.youtube.com/watch?v=q3BilWL1fCE", note: "最大高度+完璧なタック" },
          { name: "トランポリンバク宙", reps: "練習", video: "https://www.youtube.com/watch?v=LH_ZPJlkWoQ", note: "空中感覚を掴む" },
          { name: "マット+スポッター付きバク宙", reps: "5-10回", video: "https://www.youtube.com/watch?v=LJPCNNPezn8", note: "Jump→Tuck hard→Spot landing" },
          { name: "立ちバク宙", reps: "挑戦", video: "https://www.youtube.com/watch?v=LJPCNNPezn8", note: "バク転がcleanになってから。絶対に焦らない" },
        ],
      },
      {
        name: "🔥 Air Flare & パワームーブ発展",
        exercises: [
          { name: "Handstand Daddy Level 2-3", reps: "コース進行", video: null, note: "Kajabiコース（下記の方法でスマホ閲覧）" },
          { name: "コインステップ→サークル", reps: "15分", video: "https://www.youtube.com/watch?v=_5rp84EOKOE", note: "Air Flareの直前プログレッション" },
          { name: "パワーコンボ練習", reps: "15分", video: null, note: "ウィンドミル→ヘイロー→フレアの流れ" },
        ],
      },
      {
        name: "⚔️ バトル準備（月2回以上）",
        exercises: [
          { name: "フルセット練習", reps: "3ラウンド×45秒", video: null, note: "トップロック→フットワーク→パワー→フリーズ" },
          { name: "異なるBPMで対応練習", reps: "15分", video: null, note: "遅いファンク〜速いブレイクビーツ" },
          { name: "動画撮影→分析", reps: "毎回", video: null, note: "自分のフォームを客観視" },
        ],
      },
    ],
    milestones: ["バク宙マット上自力", "Air Flare 1回", "バトル3ラウンド完走", "自分のスタイルでセット構成", "ケガなし"],
  },
];

export const KAJABI_INFO: KajabiInfo = {
  title: "📱 Handstand Daddy をジムで見る方法",
  methods: [
    {
      name: "✅ Kajabiモバイルアプリ（最も簡単）",
      steps: [
        "App Store / Google Playで「Kajabi」アプリをインストール",
        "Handstand Daddyアカウントでログイン",
        "Full Airflare Course → Level 1を選択",
        "ジムのWi-Fi or モバイル回線でストリーミング再生",
      ],
      note: "📶 ジムにWi-Fiがあればベスト。なければ4G/5Gで。動画は短いのでデータ量は少なめ。",
    },
    {
      name: "💾 オフライン保存したい場合",
      steps: [
        "PCでKajabiにログイン→レッスンを開く",
        "動画プレーヤー下「Video Actions」→「Download Video」を探す",
        "あればMP4でダウンロード→AirDrop/iCloudでスマホへ",
        "なければChrome拡張「Video DownloadHelper」で保存可能",
      ],
      note: "⚠️ ダウンロード可否はHandstand Daddyの設定次第。個人学習用の保存は一般的に問題ないが、気になるならDMで確認を。",
    },
    {
      name: "🎬 コースURL（ブックマーク推奨）",
      steps: [
        "Level 1: handstand-daddy.mykajabi.com → Full Airflare Course",
        "↑をスマホのブラウザでブックマーク or ホーム画面に追加",
      ],
      note: "Braveブラウザでもアクセス可。アプリの方が使いやすい。",
    },
  ],
};

export const INJURY_PREVENTION: InjuryPrevention = {
  title: "🛡️ 40代の怪我予防 — 必読",
  items: [
    { icon: "🫀", title: "脈拍40bpm → 循環器チェック必須", desc: "激しいアクロバット前に心電図を。スポーツ心臓か病的徐脈か確認。札幌市内の循環器内科へ。" },
    { icon: "🩻", title: "腰痛 → デッドバグとブリッジを毎日", desc: "バク転の着地衝撃は腰に直結。痛みが出たら即中止。無理して壊すと半年ロスする。" },
    { icon: "🤚", title: "手首 → 最も壊れやすい部位", desc: "パワームーブ・倒立で酷使。練習前の手首ウォームアップ必須。ライスバケットを家に常備。" },
    { icon: "🦵", title: "膝 → 着地の衝撃を吸収する筋力が必要", desc: "バク転・バク宙の着地で膝を壊す人が多い。スクワット・ランジで脚を強くしてから挑戦。" },
    { icon: "🧊", title: "回復 → 41歳は10代の3倍かかる", desc: "週1-2日は完全休養。睡眠7時間以上。練習後のストレッチとアイシングを習慣化。" },
    { icon: "🥗", title: "栄養 → 関節と血管のために", desc: "タンパク質120g/日、緑黄色野菜毎食、コラーゲン+ビタミンC、水2L。内臓脂肪Lv12→8へ。" },
  ],
};
