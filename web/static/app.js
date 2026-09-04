const DEFAULT_UPLOAD_PARALLEL = 3;
const MIN_UPLOAD_PARALLEL = 1;
const MAX_UPLOAD_PARALLEL = 8;

const READER_PROGRESS_STORAGE_KEY = "book-pro-reader-progress";

registerI18nMessages({
  ko: {
    brand_sub: "다권 요약 허브",
    nav_library: "라이브러리",
    nav_detail: "책 상세",
    nav_settings: "설정",
    library_title: "Books Library",
    detail_title_default: "Book Detail",
    settings_title: "Settings",
    tip_title: "EPUB 다권 업로드",
    tip_body: "여러 권을 한번에 업로드하고 책별 챕터/캐릭터/세계관 요약을 저장합니다.",
    tip_title_library: "EPUB 다권 업로드",
    tip_body_library: "여러 권을 한번에 업로드하고 책별 챕터/캐릭터/세계관 요약을 저장합니다.",
    tip_title_detail: "EPUB 업로드",
    tip_body_detail: "Library에서 책을 선택하고 요약을 생성하거나 갱신하세요.",
    tip_title_settings: "Provider 설정",
    tip_body_settings: "기본 모델과 업로드 자동 요약 여부를 설정하세요.",
    library_subtitle: "여러 권을 등록하고 책별 상세 요약 페이지로 이동하세요.",
    upload_books_btn: "EPUB 여러권 업로드",
    metric_total_books_label: "등록된 책",
    metric_total_books_meta: "라이브러리 전체",
    metric_processing_label: "처리 중",
    metric_processing_meta: "현재 실행중",
    metric_completed_label: "완료",
    metric_completed_meta: "열람 가능",
    books_table_title: "책 목록",
    th_title: "제목",
    th_status: "상태",
    th_updated: "최근 업데이트",
    th_chapters: "챕터",
    th_characters: "캐릭터",
    th_action: "액션",
    pagination_prev: "이전",
    pagination_next: "다음",
    tab_chapter: "챕터",
    tab_character: "캐릭터",
    tab_world: "세계관",
    tab_reader: "리더",
    tab_chat: "채팅형",
    chat_loading: "채팅형 대본을 불러오는 중입니다.",
    chat_empty: "아직 생성된 채팅형 대본이 없습니다.",
    chat_generate_btn: "채팅형으로 변환",
    chat_regenerate_btn: "다시 생성",
    chat_generating: "채팅형 대본 생성 중입니다. 잠시만 기다려주세요.",
    chat_generate_done: "채팅형 변환이 완료되었습니다.",
    chat_generate_failed: "채팅형 변환에 실패했습니다.",
    tab_ask: "질문",
    tab_ask_book: "책에 대해 물어보기",
    tab_ask_character: "캐릭터와 대화하기",
    detail_subtitle_empty: "Library에서 책을 선택하면 상세 요약이 표시됩니다.",
    upload_single_btn: "EPUB 업로드",
    detail_metric_chapters_label: "챕터",
    detail_metric_chapters_meta: "분석된 챕터 수",
    detail_metric_characters_label: "캐릭터",
    detail_metric_characters_meta: "추출된 캐릭터",
    detail_metric_updated_label: "최근 업데이트",
    detail_metric_updated_meta: "저장 기준",
    quick_insights_title: "빠른 인사이트",
    insight_book_select: "책을 선택하세요.",
    generate_new_summary_btn: "새 요약 생성",
    settings_subtitle: "기본 Provider/Model을 설정하고 Provider별 API Key를 관리합니다.",
    settings_save_btn: "설정 저장",
    settings_basic_title: "기본 실행 설정",
    settings_default_provider: "기본 Provider",
    settings_default_model: "기본 Model",
    settings_custom_model: "직접 입력 Model",
    settings_custom_model_placeholder: "예: gpt-4.1-mini",
    settings_ui_language: "UI 언어",
    settings_default_language: "요약 Language",
    settings_upload_parallel: "업로드 병렬 수",
    settings_precise_analysis: "정밀 분석 사용",
    settings_auto_summarize_upload: "업로드 시 자동 요약",
    settings_hint:
      "Model은 리스트에서 선택합니다. 목록에 없으면 직접 입력 Model을 사용하세요. 업로드 병렬 수는 1~8 범위입니다. 정밀 분석을 켜면 챕터별 캐릭터 특징과 작가 필체 분석을 추가해 정확도를 높입니다. 자동 요약을 끄면 업로드 후 수동으로 요약을 실행할 수 있습니다.",
    settings_api_key_title: "Provider별 API Key",
    settings_summary:
      "현재 기본값: {provider} / {model} / API Key {apiKeyState} / 업로드 병렬 {uploadParallel} / 정밀 분석 {precise} / 업로드 자동 요약 {auto}",
    bool_on: "ON",
    bool_off: "OFF",
    model_not_set: "모델 미설정",
    api_key_set: "설정됨",
    api_key_unset: "미설정",
    custom_model_option: "직접 입력",
    models_empty: "{provider} 모델 목록이 비어 있습니다.",
    models_fetch_failed: "{provider} 모델 목록 조회 실패",
    upload_waiting: "업로드 대기 중",
    stage_queued: "업로드 대기 중",
    stage_upload: "업로드 파일 수신 중",
    stage_parse: "EPUB 파싱 중",
    stage_start: "요약 시작",
    stage_chapter: "챕터 요약 중",
    stage_character: "캐릭터 요약 중",
    stage_world: "세계관 요약 중",
    stage_style: "작가 필체 분석 중",
    stage_saving: "Markdown 저장 중",
    stage_done: "요약 완료",
    stage_failed: "요약 실패",
    pending_stage_chapter: "챕터 {index}/{total}{titlePart}",
    pending_stage_character: "캐릭터 {index}/{total}{namePart}",
    page_info: "페이지 {page} / {total}",
    status_processing: "요약 중",
    status_queued: "대기 중",
    status_failed: "실패",
    status_completed: "완료",
    table_action_open: "열기",
    table_action_summarize: "요약",
    table_progressing: "진행 중",
    empty_books_table: "저장된 책이 없습니다. EPUB 업로드 후 시작하세요.",
    reader_loading: "원문 EPUB를 불러오는 중입니다.",
    reader_no_chapters: "{title} 원문 챕터가 없습니다.",
    reader_load_failed: "원문 EPUB를 불러오지 못했습니다.",
    reader_chapter_prefix: "챕터",
    reader_progress_saved: "읽은 위치를 자동 저장합니다.",
    reader_keyboard_hint: "좌우 화살표 키로 페이지를 넘길 수 있습니다.",
    reader_empty_text: "본문이 비어 있습니다.",
    insight_stats: "챕터 {chapters}개 · 캐릭터 {characters}개",
    empty_chapter_summary: "챕터 요약이 없습니다.",
    summary_text_missing: "요약 텍스트가 없습니다.",
    view_original: "원문 보기",
    empty_character_summary: "캐릭터 요약이 없습니다.",
    world_missing: "setting.md가 없습니다.",
    upload_start: "업로드 시작",
    upload_saved: "업로드 완료 (요약 대기)",
    summary_done: "요약 완료",
    summary_failed: "요약 실패",
    config_error: "설정 오류",
    upload_error: "업로드 실패",
    result_with_error: "완료 {success}권 / 실패 {failure}권 - {error}",
    result_summary: "완료 {success}권 / 실패 {failure}권",
    result_upload_only: "업로드 완료 {success}권 / 실패 {failure}권",
    settings_saved: "설정을 저장했습니다.",
    select_book_first: "먼저 Library에서 책을 선택하세요.",
    init_load_failed: "초기 로딩 실패",
    ask_mode: "모드",
    ask_mode_book: "책에 대해 물어보기",
    ask_mode_character: "캐릭터와 대화하기",
    ask_character: "캐릭터 이름",
    ask_character_select_placeholder: "캐릭터를 선택하세요",
    ask_question: "질문",
    ask_submit: "질문하기",
    ask_empty: "질문하면 답변이 표시됩니다.",
    ask_need_question: "질문을 입력하세요.",
    ask_need_character: "캐릭터 이름을 입력하세요.",
    ask_loading: "답변 생성 중...",
  },
  en: {
    brand_sub: "Multi-book Summary Hub",
    nav_library: "Library",
    nav_detail: "Book Detail",
    nav_settings: "Settings",
    library_title: "Books Library",
    detail_title_default: "Book Detail",
    settings_title: "Settings",
    tip_title: "Upload Multiple EPUBs",
    tip_body: "Upload multiple books and save chapter/character/world summaries per book.",
    tip_title_library: "Upload Multiple EPUBs",
    tip_body_library: "Upload multiple books and save chapter/character/world summaries per book.",
    tip_title_detail: "Upload EPUB",
    tip_body_detail: "Select a book in Library and generate or refresh summaries.",
    tip_title_settings: "Provider Configuration",
    tip_body_settings: "Choose default model and whether uploads should auto-start summarization.",
    library_subtitle: "Register books and open each book detail page.",
    upload_books_btn: "Upload EPUBs",
    metric_total_books_label: "Books",
    metric_total_books_meta: "All library items",
    metric_processing_label: "Processing",
    metric_processing_meta: "Currently running",
    metric_completed_label: "Completed",
    metric_completed_meta: "Ready to view",
    books_table_title: "Books",
    th_title: "Title",
    th_status: "Status",
    th_updated: "Updated",
    th_chapters: "Chapters",
    th_characters: "Characters",
    th_action: "Action",
    pagination_prev: "Prev",
    pagination_next: "Next",
    tab_chapter: "Chapter",
    tab_character: "Character",
    tab_world: "World",
    tab_reader: "Reader",
    tab_chat: "Chat",
    chat_loading: "Loading chat script...",
    chat_empty: "No chat script generated yet.",
    chat_generate_btn: "Convert to chat",
    chat_regenerate_btn: "Regenerate",
    chat_generating: "Generating chat script, please wait...",
    chat_generate_done: "Chat script generated.",
    chat_generate_failed: "Failed to generate chat script.",
    tab_ask: "Ask",
    tab_ask_book: "Ask about book",
    tab_ask_character: "Talk with character",
    detail_subtitle_empty: "Select a book in Library to view details.",
    upload_single_btn: "Upload EPUB",
    detail_metric_chapters_label: "Chapters",
    detail_metric_chapters_meta: "Summarized chapters",
    detail_metric_characters_label: "Characters",
    detail_metric_characters_meta: "Extracted profiles",
    detail_metric_updated_label: "Updated",
    detail_metric_updated_meta: "Saved timestamp",
    quick_insights_title: "Quick Insights",
    insight_book_select: "Select a book.",
    generate_new_summary_btn: "Generate New Summary",
    settings_subtitle: "Set default provider/model and manage API keys by provider.",
    settings_save_btn: "Save Settings",
    settings_basic_title: "Default Run Settings",
    settings_default_provider: "Default Provider",
    settings_default_model: "Default Model",
    settings_custom_model: "Custom Model",
    settings_custom_model_placeholder: "e.g. gpt-4.1-mini",
    settings_ui_language: "UI Language",
    settings_default_language: "Summary Language",
    settings_upload_parallel: "Upload Parallelism",
    settings_precise_analysis: "Enable Precise Analysis",
    settings_auto_summarize_upload: "Auto summarize on upload",
    settings_hint:
      "Pick model from the list. If missing, use custom model. Upload parallelism range is 1~8. Precise analysis adds chapter-level character traits and writing-style analysis. If auto summarize is off, uploads are saved first and summarized manually.",
    settings_api_key_title: "API Keys by Provider",
    settings_summary:
      "Current defaults: {provider} / {model} / API Key {apiKeyState} / Parallel {uploadParallel} / Precise {precise} / Auto summarize {auto}",
    bool_on: "ON",
    bool_off: "OFF",
    model_not_set: "Model not set",
    api_key_set: "configured",
    api_key_unset: "not configured",
    custom_model_option: "Custom input",
    models_empty: "{provider} model list is empty.",
    models_fetch_failed: "Failed to load {provider} models",
    upload_waiting: "Waiting for upload",
    stage_queued: "Waiting for upload",
    stage_upload: "Receiving upload file",
    stage_parse: "Parsing EPUB",
    stage_start: "Starting summary",
    stage_chapter: "Summarizing chapters",
    stage_character: "Summarizing characters",
    stage_world: "Summarizing world",
    stage_style: "Analyzing writing style",
    stage_saving: "Saving markdown",
    stage_done: "Summary completed",
    stage_failed: "Summary failed",
    pending_stage_chapter: "Chapter {index}/{total}{titlePart}",
    pending_stage_character: "Character {index}/{total}{namePart}",
    page_info: "Page {page} / {total}",
    status_processing: "Processing",
    status_queued: "Queued",
    status_failed: "Failed",
    status_completed: "Completed",
    table_action_open: "Open",
    table_action_summarize: "Summarize",
    table_progressing: "In progress",
    empty_books_table: "No saved books yet. Upload an EPUB to start.",
    reader_loading: "Loading EPUB original text...",
    reader_no_chapters: "No readable chapters in {title}.",
    reader_load_failed: "Failed to load EPUB original text.",
    reader_chapter_prefix: "Chapter",
    reader_progress_saved: "Reading position is auto-saved.",
    reader_keyboard_hint: "Use left/right arrow keys to turn pages.",
    reader_empty_text: "No readable text in this chapter.",
    insight_stats: "Chapters {chapters} · Characters {characters}",
    empty_chapter_summary: "No chapter summaries.",
    summary_text_missing: "Summary text is missing.",
    view_original: "View source",
    empty_character_summary: "No character summaries.",
    world_missing: "setting.md is missing.",
    upload_start: "Upload started",
    upload_saved: "Uploaded (waiting for summary)",
    summary_done: "Summary completed",
    summary_failed: "Summary failed",
    config_error: "Configuration error",
    upload_error: "Upload failed",
    result_with_error: "Done {success} / Failed {failure} - {error}",
    result_summary: "Done {success} / Failed {failure}",
    result_upload_only: "Uploaded {success} / Failed {failure}",
    settings_saved: "Settings saved.",
    select_book_first: "Select a book from Library first.",
    init_load_failed: "Initial load failed",
    ask_mode: "Mode",
    ask_mode_book: "Ask about book",
    ask_mode_character: "Talk with character",
    ask_character: "Character name",
    ask_character_select_placeholder: "Select a character",
    ask_question: "Question",
    ask_submit: "Ask",
    ask_empty: "Answers will appear here.",
    ask_need_question: "Enter a question.",
    ask_need_character: "Enter a character name.",
    ask_loading: "Generating answer...",
  },
  ja: {
    brand_sub: "マルチブック要約ハブ",
    nav_library: "ライブラリ",
    nav_detail: "本の詳細",
    nav_settings: "設定",
    library_title: "Books Library",
    detail_title_default: "Book Detail",
    settings_title: "Settings",
    tip_title: "EPUB 複数アップロード",
    tip_body: "複数の本を一括アップロードし、本ごとの章/キャラクター/世界観要約を保存します。",
    tip_title_library: "EPUB 複数アップロード",
    tip_body_library: "複数の本を一括アップロードし、本ごとの章/キャラクター/世界観要約を保存します。",
    tip_title_detail: "EPUB アップロード",
    tip_body_detail: "Library で本を選択し、要約を生成または更新します。",
    tip_title_settings: "Provider 設定",
    tip_body_settings: "デフォルトモデルとアップロード時の自動要約を設定します。",
    library_subtitle: "複数の本を登録し、各本の詳細ページを開きます。",
    upload_books_btn: "EPUB をアップロード",
    metric_total_books_label: "本",
    metric_total_books_meta: "ライブラリ全体",
    metric_processing_label: "処理中",
    metric_processing_meta: "現在実行中",
    metric_completed_label: "完了",
    metric_completed_meta: "閲覧可能",
    books_table_title: "本一覧",
    th_title: "タイトル",
    th_status: "状態",
    th_updated: "更新日時",
    th_chapters: "章",
    th_characters: "キャラクター",
    th_action: "操作",
    pagination_prev: "前へ",
    pagination_next: "次へ",
    tab_chapter: "章",
    tab_character: "キャラクター",
    tab_world: "世界観",
    tab_reader: "リーダー",
    tab_ask: "質問",
    tab_ask_book: "本について質問",
    tab_ask_character: "キャラクターと会話",
    detail_subtitle_empty: "ライブラリで本を選択すると詳細が表示されます。",
    upload_single_btn: "EPUB アップロード",
    detail_metric_chapters_label: "章",
    detail_metric_chapters_meta: "要約済み章数",
    detail_metric_characters_label: "キャラクター",
    detail_metric_characters_meta: "抽出されたプロフィール",
    detail_metric_updated_label: "更新日時",
    detail_metric_updated_meta: "保存基準",
    quick_insights_title: "クイックインサイト",
    insight_book_select: "本を選択してください。",
    generate_new_summary_btn: "新しい要約を生成",
    settings_subtitle: "デフォルト Provider/Model を設定し、Provider ごとの API Key を管理します。",
    settings_save_btn: "設定を保存",
    settings_basic_title: "デフォルト実行設定",
    settings_default_provider: "デフォルト Provider",
    settings_default_model: "デフォルト Model",
    settings_custom_model: "カスタム Model",
    settings_custom_model_placeholder: "例: gpt-4.1-mini",
    settings_ui_language: "UI 言語",
    settings_default_language: "要約言語",
    settings_upload_parallel: "アップロード並列数",
    settings_precise_analysis: "精密分析を有効化",
    settings_auto_summarize_upload: "アップロード時に自動要約",
    settings_hint:
      "Model はリストから選択します。なければカスタム Model を使用します。アップロード並列数は 1〜8。精密分析を有効にすると章ごとのキャラクター特徴と文体分析を追加します。自動要約をオフにすると、アップロード後に手動で要約を実行できます。",
    settings_api_key_title: "Provider 別 API Key",
    settings_summary:
      "現在の既定値: {provider} / {model} / API Key {apiKeyState} / 並列 {uploadParallel} / 精密分析 {precise} / 自動要約 {auto}",
    bool_on: "ON",
    bool_off: "OFF",
    model_not_set: "Model 未設定",
    api_key_set: "設定済み",
    api_key_unset: "未設定",
    custom_model_option: "直接入力",
    models_empty: "{provider} のモデル一覧が空です。",
    models_fetch_failed: "{provider} のモデル一覧取得に失敗しました",
    upload_waiting: "アップロード待機中",
    stage_queued: "アップロード待機中",
    stage_upload: "アップロードファイル受信中",
    stage_parse: "EPUB 解析中",
    stage_start: "要約開始",
    stage_chapter: "章要約中",
    stage_character: "キャラクター要約中",
    stage_world: "世界観要約中",
    stage_style: "文体分析中",
    stage_saving: "Markdown 保存中",
    stage_done: "要約完了",
    stage_failed: "要約失敗",
    pending_stage_chapter: "章 {index}/{total}{titlePart}",
    pending_stage_character: "キャラクター {index}/{total}{namePart}",
    page_info: "ページ {page} / {total}",
    status_processing: "要約中",
    status_queued: "待機中",
    status_failed: "失敗",
    status_completed: "完了",
    table_action_open: "開く",
    table_action_summarize: "要約",
    table_progressing: "進行中",
    empty_books_table: "保存された本がありません。EPUB をアップロードしてください。",
    reader_loading: "EPUB 原文を読み込み中です...",
    reader_no_chapters: "{title} に読める章がありません。",
    reader_load_failed: "EPUB 原文の読み込みに失敗しました。",
    reader_chapter_prefix: "章",
    reader_progress_saved: "読書位置は自動で保存されます。",
    reader_keyboard_hint: "左右の矢印キーでページをめくれます。",
    reader_empty_text: "本文が空です。",
    insight_stats: "章 {chapters} · キャラクター {characters}",
    empty_chapter_summary: "章要約がありません。",
    summary_text_missing: "要約テキストがありません。",
    view_original: "原文を見る",
    empty_character_summary: "キャラクター要約がありません。",
    world_missing: "setting.md がありません。",
    upload_start: "アップロード開始",
    upload_saved: "アップロード完了（要約待ち）",
    summary_done: "要約完了",
    summary_failed: "要約失敗",
    config_error: "設定エラー",
    upload_error: "アップロード失敗",
    result_with_error: "完了 {success} / 失敗 {failure} - {error}",
    result_summary: "完了 {success} / 失敗 {failure}",
    result_upload_only: "アップロード完了 {success} / 失敗 {failure}",
    settings_saved: "設定を保存しました。",
    select_book_first: "先に Library で本を選択してください。",
    init_load_failed: "初期読み込みに失敗しました",
    ask_mode: "モード",
    ask_mode_book: "本について質問",
    ask_mode_character: "キャラクターと会話",
    ask_character: "キャラクター名",
    ask_character_select_placeholder: "キャラクターを選択してください",
    ask_question: "質問",
    ask_submit: "質問する",
    ask_empty: "質問すると回答が表示されます。",
    ask_need_question: "質問を入力してください。",
    ask_need_character: "キャラクター名を入力してください。",
    ask_loading: "回答を生成中...",
  },
});

function clampUploadParallel(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return DEFAULT_UPLOAD_PARALLEL;
  const rounded = Math.trunc(numeric);
  return Math.max(MIN_UPLOAD_PARALLEL, Math.min(MAX_UPLOAD_PARALLEL, rounded));
}

const state = {
  page: 1,
  pageSize: 10,
  total: 0,
  items: [],
  pendingUploads: [],
  nextPendingId: 1,
  currentBook: null,
  readerCache: {},
  readerRequestSeq: 0,
  readerProgress: {},
  readerProgressSync: {},
  readerRuntime: null,
  chatCache: null,
  currentTab: "chapter",
  currentView: "library",
  uploading: false,
  pendingUploadMode: "multi",
  modelOptions: {},
  modelOptionsLoaded: {},
  settings: {
    selectedProvider: "open-ai",
    uiLanguage: "ko",
    language: "ko",
    uploadParallel: DEFAULT_UPLOAD_PARALLEL,
    preciseAnalysis: false,
    autoSummarizeOnUpload: false,
    models: { ...DEFAULT_MODEL_BY_PROVIDER },
    apiKeys: {
      "open-ai": "",
      anthropic: "",
      openrouter: "",
      venice: "",
      "kilo-code": "",
      "opencode-go": "",
      "opencode-zen": "",
    },
  },
};

const el = {
  navLibrary: document.getElementById("nav-library"),
  navDetail: document.getElementById("nav-detail"),
  navSettings: document.getElementById("nav-settings"),

  viewLibrary: document.getElementById("view-library"),
  viewDetail: document.getElementById("view-detail"),
  viewSettings: document.getElementById("view-settings"),

  settingsProviderSelect: document.getElementById("settings-provider-select"),
  settingsModelSelect: document.getElementById("settings-model-select"),
  settingsCustomModelField: document.getElementById("settings-custom-model-field"),
  settingsCustomModelInput: document.getElementById("settings-custom-model-input"),
  settingsUiLanguageInput: document.getElementById("settings-ui-language-input"),
  settingsLanguageInput: document.getElementById("settings-language-input"),
  settingsUploadParallelInput: document.getElementById("settings-upload-parallel-input"),
  settingsPreciseAnalysisInput: document.getElementById("settings-precise-analysis-input"),
  settingsAutoSummarizeInput: document.getElementById("settings-auto-summarize-upload-input"),
  apiKeyOpenAi: document.getElementById("api-key-open-ai"),
  apiKeyAnthropic: document.getElementById("api-key-anthropic"),
  apiKeyOpenrouter: document.getElementById("api-key-openrouter"),
  apiKeyVenice: document.getElementById("api-key-venice"),
  apiKeyKiloCode: document.getElementById("api-key-kilo-code"),
  apiKeyOpencodeGo: document.getElementById("api-key-opencode-go"),
  apiKeyOpencodeZen: document.getElementById("api-key-opencode-zen"),
  settingsSaveBtn: document.getElementById("settings-save-btn"),
  settingsActiveSummary: document.getElementById("settings-active-summary"),

  uploadBooksBtn: document.getElementById("upload-books-btn"),
  uploadSingleBtn: document.getElementById("upload-single-btn"),
  generateFromDetailBtn: document.getElementById("generate-from-detail-btn"),
  fileInput: document.getElementById("epub-file-input"),

  metricTotalBooks: document.getElementById("metric-total-books"),
  metricProcessingBooks: document.getElementById("metric-processing-books"),
  metricCompletedBooks: document.getElementById("metric-completed-books"),

  booksTableBody: document.getElementById("books-table-body"),
  libraryPageInfo: document.getElementById("library-page-info"),
  prevPageBtn: document.getElementById("prev-page-btn"),
  nextPageBtn: document.getElementById("next-page-btn"),

  detailTitle: document.getElementById("detail-title"),
  detailSubtitle: document.getElementById("detail-subtitle"),
  detailChapterCount: document.getElementById("detail-chapter-count"),
  detailCharacterCount: document.getElementById("detail-character-count"),
  detailUpdatedAt: document.getElementById("detail-updated-at"),

  tabButtons: Array.from(document.querySelectorAll(".tab")),
  tabChapter: document.getElementById("tab-chapter"),
  tabCharacter: document.getElementById("tab-character"),
  tabWorld: document.getElementById("tab-world"),
  tabReader: document.getElementById("tab-reader"),
  tabChat: document.getElementById("tab-chat"),
  tabAskBook: document.getElementById("tab-ask-book"),
  tabAskCharacter: document.getElementById("tab-ask-character"),
  askBookQuestionInput: document.getElementById("ask-book-question-input"),
  askBookSubmitBtn: document.getElementById("ask-book-submit-btn"),
  askBookAnswer: document.getElementById("ask-book-answer"),
  askCharacterSelect: document.getElementById("ask-character-select"),
  askCharacterQuestionInput: document.getElementById("ask-character-question-input"),
  askCharacterSubmitBtn: document.getElementById("ask-character-submit-btn"),
  askCharacterAnswer: document.getElementById("ask-character-answer"),

  insightBookTitle: document.getElementById("insight-book-title"),
  insightBookStats: document.getElementById("insight-book-stats"),

  toast: document.getElementById("toast"),
};

function formatDate(iso) {
  if (!iso) return "-";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const localeByUi = {
    ko: "ko-KR",
    en: "en-US",
    ja: "ja-JP",
  };
  const locale = localeByUi[normalizeUiLanguage(state.settings?.uiLanguage || "ko")] || "ko-KR";
  return date.toLocaleString(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function createDefaultSettings() {
  return {
    selectedProvider: "open-ai",
    uiLanguage: "ko",
    language: "ko",
    uploadParallel: DEFAULT_UPLOAD_PARALLEL,
    preciseAnalysis: false,
    autoSummarizeOnUpload: false,
    models: { ...DEFAULT_MODEL_BY_PROVIDER },
    apiKeys: {
      "open-ai": "",
      anthropic: "",
      openrouter: "",
      venice: "",
      "kilo-code": "",
      "opencode-go": "",
      "opencode-zen": "",
    },
  };
}

function normalizeProvider(value) {
  return PROVIDERS.includes(value) ? value : "open-ai";
}

function sortModelsAlphabetically(models) {
  return [...models].sort((a, b) => a.localeCompare(b, "en", { sensitivity: "base", numeric: true }));
}

function initializeModelOptionState() {
  PROVIDERS.forEach((provider) => {
    const defaults = MODEL_OPTIONS_BY_PROVIDER[provider] || [];
    state.modelOptions[provider] = sortModelsAlphabetically(defaults);
    state.modelOptionsLoaded[provider] = false;
  });
}

function loadSettingsFromStorage() {
  const defaults = createDefaultSettings();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      state.settings = defaults;
      renderSettingsForm();
      return;
    }

    const parsed = JSON.parse(raw);
    const selectedProvider = normalizeProvider(parsed.selectedProvider || parsed.provider || "open-ai");
    const uiLanguage = normalizeUiLanguage(parsed.uiLanguage || parsed.ui_language || "ko");
    const language = typeof parsed.language === "string" && parsed.language.trim() ? parsed.language.trim() : "ko";
    const uploadParallel = clampUploadParallel(parsed.uploadParallel ?? parsed.maxParallel);
    const preciseAnalysis = parsed.preciseAnalysis === true || parsed.preciseAnalysis === "true";
    const autoSummarizeOnUpload =
      parsed.autoSummarizeOnUpload === true ||
      parsed.autoSummarizeOnUpload === "true" ||
      parsed.autoSummarizeUpload === true ||
      parsed.autoSummarizeUpload === "true";

    const models = { ...DEFAULT_MODEL_BY_PROVIDER };
    if (parsed.models && typeof parsed.models === "object") {
      PROVIDERS.forEach((provider) => {
        const candidate = parsed.models[provider];
        if (typeof candidate === "string" && candidate.trim()) {
          models[provider] = candidate.trim();
        }
      });
    }
    if (typeof parsed.model === "string" && parsed.model.trim()) {
      models[selectedProvider] = parsed.model.trim();
    }

    const apiKeys = { ...defaults.apiKeys };
    if (parsed.apiKeys && typeof parsed.apiKeys === "object") {
      PROVIDERS.forEach((provider) => {
        const key = parsed.apiKeys[provider];
        if (typeof key === "string") {
          apiKeys[provider] = key;
        }
      });
    }
    if (typeof parsed.apiKey === "string" && parsed.apiKey.trim()) {
      apiKeys[selectedProvider] = parsed.apiKey.trim();
    }

    state.settings = {
      selectedProvider,
      uiLanguage,
      language,
      uploadParallel,
      preciseAnalysis,
      autoSummarizeOnUpload,
      models,
      apiKeys,
    };
  } catch (_error) {
    state.settings = defaults;
  }

  applyI18nToDom(state.settings?.uiLanguage);
  renderSettingsForm();
}

function persistSettings() {
  const provider = state.settings.selectedProvider;
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      selectedProvider: provider,
      provider,
      uiLanguage: normalizeUiLanguage(state.settings.uiLanguage),
      language: state.settings.language,
      uploadParallel: clampUploadParallel(state.settings.uploadParallel),
      maxParallel: clampUploadParallel(state.settings.uploadParallel),
      preciseAnalysis: Boolean(state.settings.preciseAnalysis),
      autoSummarizeOnUpload: Boolean(state.settings.autoSummarizeOnUpload),
      autoSummarizeUpload: Boolean(state.settings.autoSummarizeOnUpload),
      models: state.settings.models,
      model: state.settings.models[provider] || "",
      apiKeys: state.settings.apiKeys,
      apiKey: state.settings.apiKeys[provider] || "",
    }),
  );
}

function normalizeReaderProgressValue(value) {
  const totalPagesRaw = value?.total_pages ?? value?.totalPages ?? 1;
  const pageRaw = value?.page ?? 0;
  const ratioRaw = value?.ratio;
  const updatedAtRaw = value?.updated_at ?? value?.updatedAt ?? "";

  const safeTotalPages = Number.isFinite(Number(totalPagesRaw)) ? Math.max(1, Math.trunc(Number(totalPagesRaw))) : 1;
  const safePage = Number.isFinite(Number(pageRaw))
    ? Math.max(0, Math.min(safeTotalPages - 1, Math.trunc(Number(pageRaw))))
    : 0;
  const safeRatio = Number.isFinite(Number(ratioRaw))
    ? Math.max(0, Math.min(1, Number(ratioRaw)))
    : safeTotalPages <= 1
      ? 0
      : safePage / Math.max(1, safeTotalPages - 1);

  return {
    page: safePage,
    totalPages: safeTotalPages,
    ratio: safeRatio,
    updatedAt: typeof updatedAtRaw === "string" ? updatedAtRaw : "",
  };
}

function setLocalReaderProgress(slug, value, { persist = true } = {}) {
  const safeSlug = (slug || "").trim();
  if (!safeSlug) return null;

  const normalized = normalizeReaderProgressValue(value || {});
  state.readerProgress[safeSlug] = normalized;
  if (persist) {
    persistReaderProgress();
  }
  return normalized;
}

function loadReaderProgressFromStorage() {
  state.readerProgress = {};
  state.readerProgressSync = {};

  try {
    const raw = localStorage.getItem(READER_PROGRESS_STORAGE_KEY);
    if (!raw) return;

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return;

    Object.entries(parsed).forEach(([slug, value]) => {
      if (!slug || typeof slug !== "string") return;
      setLocalReaderProgress(slug, value, { persist: false });
    });
  } catch (_error) {
    state.readerProgress = {};
  }
}

function persistReaderProgress() {
  try {
    localStorage.setItem(READER_PROGRESS_STORAGE_KEY, JSON.stringify(state.readerProgress));
  } catch (_error) {
    // 로컬스토리지 저장 실패(시크릿 모드 등)는 무시한다.
  }
}

function queueReaderProgressSync(slug, progress) {
  const safeSlug = (slug || "").trim();
  if (!safeSlug) return;

  const normalized = normalizeReaderProgressValue(progress || {});
  const slot = state.readerProgressSync[safeSlug] || { inFlight: false, next: null };
  slot.next = normalized;
  state.readerProgressSync[safeSlug] = slot;

  if (slot.inFlight) {
    return;
  }

  const flush = async () => {
    const current = state.readerProgressSync[safeSlug];
    if (!current || !current.next) return;

    current.inFlight = true;
    const payload = current.next;
    current.next = null;

    try {
      const response = await fetchJson(`/books/${encodeURIComponent(safeSlug)}/reader/progress`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page: payload.page,
          total_pages: payload.totalPages,
          ratio: payload.ratio,
        }),
      });
      setLocalReaderProgress(safeSlug, response);
    } catch (_error) {
      // 네트워크 오류 시 다음 저장에서 재시도한다.
    } finally {
      const latest = state.readerProgressSync[safeSlug];
      if (!latest) return;
      latest.inFlight = false;
      if (latest.next) {
        void flush();
      }
    }
  };

  void flush();
}

async function loadReaderProgressFromServer(slug, { force = false } = {}) {
  const safeSlug = (slug || "").trim();
  if (!safeSlug) return null;

  if (!force && state.readerProgress[safeSlug]) {
    return state.readerProgress[safeSlug];
  }

  try {
    const payload = await fetchJson(`/books/${encodeURIComponent(safeSlug)}/reader/progress`);
    return setLocalReaderProgress(safeSlug, payload);
  } catch (_error) {
    return state.readerProgress[safeSlug] || null;
  }
}

function saveReaderProgress(slug, page, totalPages, { syncServer = false } = {}) {
  const saved = setLocalReaderProgress(slug, {
    page,
    total_pages: totalPages,
    updated_at: new Date().toISOString(),
  });
  if (!saved) return null;

  if (syncServer) {
    queueReaderProgressSync(slug, saved);
  }
  return saved;
}

function resolveSavedReaderPage(slug, totalPages) {
  const safeSlug = (slug || "").trim();
  if (!safeSlug) return 0;

  const safeTotal = Math.max(1, Math.trunc(Number(totalPages) || 1));
  const saved = state.readerProgress[safeSlug];
  if (!saved || typeof saved !== "object") return 0;

  if (Number.isFinite(saved.ratio)) {
    return Math.max(0, Math.min(safeTotal - 1, Math.round(saved.ratio * Math.max(0, safeTotal - 1))));
  }

  if (Number.isFinite(saved.page) && Number.isFinite(saved.totalPages) && saved.totalPages > 0) {
    const ratio = saved.totalPages <= 1 ? 0 : saved.page / Math.max(1, saved.totalPages - 1);
    return Math.max(0, Math.min(safeTotal - 1, Math.round(ratio * Math.max(0, safeTotal - 1))));
  }

  return 0;
}

function renderSettingsSummary() {
  if (!el.settingsActiveSummary) return;

  const provider = state.settings.selectedProvider;
  const providerLabel = PROVIDER_LABEL[provider] || provider;
  const model = state.settings.models[provider] || "";
  const hasKey = Boolean(state.settings.apiKeys[provider]);
  const uploadParallel = clampUploadParallel(state.settings.uploadParallel);
  const preciseText = state.settings.preciseAnalysis ? t("bool_on") : t("bool_off");
  const autoText = state.settings.autoSummarizeOnUpload ? t("bool_on") : t("bool_off");
  const modelText = model || t("model_not_set");

  el.settingsActiveSummary.textContent = t("settings_summary", {
    provider: providerLabel,
    model: modelText,
    apiKeyState: hasKey ? t("api_key_set") : t("api_key_unset"),
    uploadParallel,
    precise: preciseText,
    auto: autoText,
  });
}

function ensureModelForProvider(provider) {
  if (!state.settings.models[provider]) {
    state.settings.models[provider] = DEFAULT_MODEL_BY_PROVIDER[provider] || "";
  }
}

function getProviderModelOptions(provider) {
  const loaded = state.modelOptions[provider];
  if (Array.isArray(loaded) && loaded.length) {
    return sortModelsAlphabetically(loaded);
  }
  return sortModelsAlphabetically(
    MODEL_OPTIONS_BY_PROVIDER[provider] || [DEFAULT_MODEL_BY_PROVIDER[provider] || ""],
  );
}

function setCustomModelVisible(visible) {
  if (!el.settingsCustomModelField) return;
  el.settingsCustomModelField.classList.toggle("hidden", !visible);
}

function renderModelSelect(provider) {
  if (!el.settingsModelSelect) return;

  ensureModelForProvider(provider);

  const activeModel = state.settings.models[provider] || "";
  const options = getProviderModelOptions(provider);
  const inList = options.includes(activeModel);

  el.settingsModelSelect.innerHTML = "";
  for (const model of options) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    el.settingsModelSelect.append(option);
  }

  const customOption = document.createElement("option");
  customOption.value = CUSTOM_MODEL_VALUE;
  customOption.textContent = t("custom_model_option");
  el.settingsModelSelect.append(customOption);

  if (inList) {
    el.settingsModelSelect.value = activeModel;
    if (el.settingsCustomModelInput) el.settingsCustomModelInput.value = "";
    setCustomModelVisible(false);
    return;
  }

  el.settingsModelSelect.value = CUSTOM_MODEL_VALUE;
  if (el.settingsCustomModelInput) el.settingsCustomModelInput.value = activeModel;
  setCustomModelVisible(true);
}

function readModelFromControls(provider) {
  const selectedValue = (el.settingsModelSelect?.value || "").trim();
  if (selectedValue === CUSTOM_MODEL_VALUE) {
    const customValue = (el.settingsCustomModelInput?.value || "").trim();
    if (customValue) {
      return customValue;
    }
    return state.settings.models[provider] || DEFAULT_MODEL_BY_PROVIDER[provider] || "";
  }
  return selectedValue || DEFAULT_MODEL_BY_PROVIDER[provider] || "";
}

async function fetchProviderModels(provider, { force = false, silent = false } = {}) {
  const normalized = normalizeProvider(provider);
  if (!force && state.modelOptionsLoaded[normalized]) {
    return;
  }

  const formData = new FormData();
  formData.append("provider", normalized);
  const apiKey = (state.settings.apiKeys[normalized] || "").trim();
  if (apiKey) {
    formData.append("api_key", apiKey);
  }

  try {
    const payload = await fetchJson("/providers/models", {
      method: "POST",
      body: formData,
    });
    const models = Array.isArray(payload.models)
      ? payload.models.map((item) => String(item)).filter((item) => item.trim().length > 0)
      : [];

    if (!models.length) {
      throw new Error(t("models_empty", { provider: PROVIDER_LABEL[normalized] }));
    }

    state.modelOptions[normalized] = sortModelsAlphabetically(models);
    state.modelOptionsLoaded[normalized] = true;

    if (!state.settings.models[normalized]) {
      state.settings.models[normalized] = models[0];
      persistSettings();
    }

    if (state.settings.selectedProvider === normalized) {
      renderSettingsForm();
    }
  } catch (error) {
    state.modelOptionsLoaded[normalized] = false;
    if (!silent) {
      showToast(error.message || t("models_fetch_failed", { provider: PROVIDER_LABEL[normalized] }), true);
    }
  }
}

function renderSettingsForm() {
  const provider = state.settings.selectedProvider;

  applyI18nToDom(state.settings?.uiLanguage);
  if (!state.currentBook && el.insightBookTitle) {
    el.insightBookTitle.textContent = t("insight_book_select");
  }

  if (el.settingsProviderSelect) {
    el.settingsProviderSelect.value = provider;
  }
  renderModelSelect(provider);
  if (el.settingsUiLanguageInput) {
    el.settingsUiLanguageInput.value = normalizeUiLanguage(state.settings.uiLanguage || "ko");
  }
  if (el.settingsLanguageInput) {
    el.settingsLanguageInput.value = state.settings.language || "ko";
  }
  if (el.settingsUploadParallelInput) {
    el.settingsUploadParallelInput.value = String(clampUploadParallel(state.settings.uploadParallel));
  }
  if (el.settingsPreciseAnalysisInput) {
    el.settingsPreciseAnalysisInput.checked = Boolean(state.settings.preciseAnalysis);
  }
  if (el.settingsAutoSummarizeInput) {
    el.settingsAutoSummarizeInput.checked = Boolean(state.settings.autoSummarizeOnUpload);
  }

  if (el.apiKeyOpenAi) el.apiKeyOpenAi.value = state.settings.apiKeys["open-ai"] || "";
  if (el.apiKeyAnthropic) el.apiKeyAnthropic.value = state.settings.apiKeys.anthropic || "";
  if (el.apiKeyOpenrouter) el.apiKeyOpenrouter.value = state.settings.apiKeys.openrouter || "";
  if (el.apiKeyVenice) el.apiKeyVenice.value = state.settings.apiKeys.venice || "";
  if (el.apiKeyKiloCode) el.apiKeyKiloCode.value = state.settings.apiKeys["kilo-code"] || "";
  if (el.apiKeyOpencodeGo) el.apiKeyOpencodeGo.value = state.settings.apiKeys["opencode-go"] || "";
  if (el.apiKeyOpencodeZen) el.apiKeyOpencodeZen.value = state.settings.apiKeys["opencode-zen"] || "";

  renderSettingsSummary();
}

function syncSettingsFromForm() {
  const prevProvider = state.settings.selectedProvider;
  const nextProvider = normalizeProvider(el.settingsProviderSelect?.value || prevProvider);

  state.settings.models[prevProvider] = readModelFromControls(prevProvider);

  state.settings.selectedProvider = nextProvider;
  state.settings.uiLanguage = normalizeUiLanguage(el.settingsUiLanguageInput?.value || state.settings.uiLanguage || "ko");
  state.settings.language = (el.settingsLanguageInput?.value || state.settings.language || "ko").trim() || "ko";
  state.settings.uploadParallel = clampUploadParallel(el.settingsUploadParallelInput?.value ?? state.settings.uploadParallel);
  state.settings.preciseAnalysis = Boolean(el.settingsPreciseAnalysisInput?.checked);
  state.settings.autoSummarizeOnUpload = Boolean(el.settingsAutoSummarizeInput?.checked);
  state.settings.apiKeys["open-ai"] = (el.apiKeyOpenAi?.value || state.settings.apiKeys["open-ai"] || "").trim();
  state.settings.apiKeys.anthropic = (el.apiKeyAnthropic?.value || state.settings.apiKeys.anthropic || "").trim();
  state.settings.apiKeys.openrouter = (el.apiKeyOpenrouter?.value || state.settings.apiKeys.openrouter || "").trim();
  state.settings.apiKeys.venice = (el.apiKeyVenice?.value || state.settings.apiKeys.venice || "").trim();
  state.settings.apiKeys["kilo-code"] = (el.apiKeyKiloCode?.value || state.settings.apiKeys["kilo-code"] || "").trim();
  state.settings.apiKeys["opencode-go"] = (el.apiKeyOpencodeGo?.value || state.settings.apiKeys["opencode-go"] || "").trim();
  state.settings.apiKeys["opencode-zen"] = (el.apiKeyOpencodeZen?.value || state.settings.apiKeys["opencode-zen"] || "").trim();

  ensureModelForProvider(nextProvider);

  persistSettings();
  renderSettingsForm();
}

function switchView(view) {
  state.currentView = view;
  el.viewLibrary.classList.toggle("active", view === "library");
  el.viewDetail.classList.toggle("active", view === "detail");
  el.viewSettings.classList.toggle("active", view === "settings");

  el.navLibrary?.classList.toggle("active", view === "library" || view === "detail");
  el.navDetail?.classList.toggle("active", view === "detail");
  el.navSettings?.classList.toggle("active", view === "settings");
}

function currentPageCount() {
  return Math.max(1, Math.ceil(state.total / state.pageSize));
}

function pendingProcessingCount() {
  return state.pendingUploads.filter((item) => item.status === "queued" || item.status === "processing").length;
}

function renderLibraryMetrics() {
  const processing = pendingProcessingCount();
  el.metricTotalBooks.textContent = String(state.total + processing);
  el.metricProcessingBooks.textContent = String(processing);
  el.metricCompletedBooks.textContent = String(state.total);
}

function generateUploadId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function findPendingUploadByUploadId(uploadId) {
  return state.pendingUploads.find((item) => item.uploadId === uploadId) || null;
}

function addPendingUpload(fileName, options = {}) {
  const id = options.id || `pending-${state.nextPendingId++}`;
  const row = {
    id,
    uploadId: options.uploadId || generateUploadId(),
    fileName,
    displayName: options.displayName || fileName,
    status: options.status || "queued",
    progress: Number.isFinite(options.progress) ? options.progress : 0,
    message: options.message || t("upload_waiting"),
    bookTitle: options.bookTitle || "",
    stage: options.stage || "queued",
    chapterIndex: options.chapterIndex ?? null,
    chapterTotal: options.chapterTotal ?? null,
    chapterTitle: options.chapterTitle || "",
    characterIndex: options.characterIndex ?? null,
    characterTotal: options.characterTotal ?? null,
    characterName: options.characterName || "",
    error: options.error || "",
    timerId: null,
    completionTimerId: null,
  };
  state.pendingUploads.unshift(row);
  renderLibraryMetrics();
  renderBooksTable(state.items);
  return row;
}

function updatePendingUpload(id, patch) {
  const row = state.pendingUploads.find((item) => item.id === id);
  if (!row) return;
  Object.assign(row, patch);
  renderLibraryMetrics();
  renderBooksTable(state.items);
}

function removePendingUpload(id) {
  const index = state.pendingUploads.findIndex((item) => item.id === id);
  if (index < 0) return;
  const [row] = state.pendingUploads.splice(index, 1);
  if (row && row.timerId) {
    window.clearInterval(row.timerId);
  }
  if (row && row.completionTimerId) {
    window.clearTimeout(row.completionTimerId);
  }
  renderLibraryMetrics();
  renderBooksTable(state.items);
}

function renderPendingMessage(item) {
  if (item.error) return item.error;

  if (item.stage === "chapter") {
    const chapterIndex = item.chapterIndex;
    const chapterTotal = item.chapterTotal;
    const chapterTitle = item.chapterTitle || "";
    if (chapterIndex && chapterTotal) {
      return t("pending_stage_chapter", {
        index: chapterIndex,
        total: chapterTotal,
        titlePart: chapterTitle ? ` - ${chapterTitle}` : "",
      });
    }
  }

  if (item.stage === "character") {
    const characterIndex = item.characterIndex;
    const characterTotal = item.characterTotal;
    const characterName = item.characterName || "";
    if (characterIndex && characterTotal) {
      return t("pending_stage_character", {
        index: characterIndex,
        total: characterTotal,
        namePart: characterName ? ` - ${characterName}` : "",
      });
    }
  }

  const stageKey = item.stage ? `stage_${item.stage}` : "";
  const stageText = stageKey ? t(stageKey) : "";
  if (stageText && stageText !== stageKey) {
    return stageText;
  }

  return item.message || "-";
}

function setUploading(isUploading) {
  state.uploading = isUploading;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

async function loadLibrary({ autoOpenFirst = false } = {}) {
  const payload = await fetchJson(`/books?page=${state.page}&page_size=${state.pageSize}`);
  state.total = payload.total;
  state.items = payload.items;

  renderLibraryMetrics();
  renderBooksTable(state.items);

  const totalPages = currentPageCount();
  el.libraryPageInfo.textContent = t("page_info", { page: state.page, total: totalPages });
  el.prevPageBtn.disabled = state.page <= 1;
  el.nextPageBtn.disabled = state.page >= totalPages;

  if (autoOpenFirst && payload.items.length > 0) {
    await openBook(payload.items[0].slug, { switchToDetail: true });
  }
}

function renderBooksTable(items) {
  const pendingRows = state.pendingUploads
    .map((item) => {
      const matched = state.items.find((book) => (book.book_title || "").trim() === (item.bookTitle || "").trim());
      const openSlug = matched?.slug || "";
      const displayTitle = escapeHtml(item.bookTitle || item.displayName || item.fileName);
      const titleCell = openSlug
        ? `<button class="inline-action table-title-action" data-open-book="${escapeHtml(openSlug)}" type="button">${displayTitle}</button>`
        : displayTitle;
      const statusLabel =
        item.status === "processing"
          ? t("status_processing")
          : item.status === "queued"
            ? t("status_queued")
            : item.status === "failed"
              ? t("status_failed")
              : t("status_completed");
      const statusClass =
        item.status === "failed"
          ? "status-failed"
          : item.status === "completed"
            ? "status-completed"
            : "status-processing";

      return `
        <tr class="pending-row">
          <td>${titleCell}</td>
          <td>
            <span class="status-chip ${statusClass}">${statusLabel}</span>
            <div class="progress-track">
              <div class="progress-fill" style="width:${Math.max(0, Math.min(item.progress || 0, 100))}%"></div>
            </div>
            <div class="progress-text">${Math.round(item.progress || 0)}%</div>
            <div class="progress-text">${escapeHtml(renderPendingMessage(item))}</div>
            ${item.error ? `<div class="error-text">${escapeHtml(item.error)}</div>` : ""}
          </td>
          <td>-</td>
          <td>-</td>
          <td>-</td>
          <td>${openSlug ? `<button class="inline-action" data-open-book="${escapeHtml(openSlug)}" type="button">${t("table_action_open")}</button>` : item.status === "processing" || item.status === "queued" ? t("table_progressing") : "-"}</td>
        </tr>
      `;
    })
    .join("");

  const processingTitles = new Set(
    state.pendingUploads
      .filter((item) => item.status === "queued" || item.status === "processing")
      .map((item) => (item.bookTitle || "").trim())
      .filter((title) => title.length > 0),
  );

  const savedRows = items
    .filter((item) => !processingTitles.has((item.book_title || "").trim()))
    .map(
      (item) => {
        const statusClass =
          item.status === "failed"
            ? "status-failed"
            : item.status === "completed"
              ? "status-completed"
              : "status-processing";
        const canSummarize = item.status === "queued" || item.status === "processing";
        return `
      <tr>
        <td>
          <button class="inline-action table-title-action" data-open-book="${escapeHtml(item.slug)}" type="button">${escapeHtml(item.book_title)}</button>
        </td>
        <td>
          <span class="status-chip ${statusClass}">
            ${escapeHtml(t(`status_${item.status}`) || item.status)}
          </span>
        </td>
        <td>${escapeHtml(formatDate(item.updated_at))}</td>
        <td>${item.chapter_count}</td>
        <td>${item.character_count}</td>
        <td>
          ${canSummarize ? `<button class="inline-action" data-summarize-book="${escapeHtml(item.slug)}" data-book-title="${escapeHtml(item.book_title)}" type="button">${t("table_action_summarize")}</button> · ` : ""}
          <button class="inline-action" data-open-book="${escapeHtml(item.slug)}" type="button">${t("table_action_open")}</button>
        </td>
      </tr>
    `;
      },
    )
    .join("");

  if (!pendingRows && !savedRows) {
    el.booksTableBody.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">${escapeHtml(t("empty_books_table"))}</td>
      </tr>
    `;
    return;
  }

  el.booksTableBody.innerHTML = `${pendingRows}${savedRows}`;

  el.booksTableBody.querySelectorAll("[data-open-book]").forEach((button) => {
    button.addEventListener("click", async () => {
      const slug = button.getAttribute("data-open-book");
      if (!slug) return;
      await openBook(slug, { switchToDetail: true });
    });
  });

  el.booksTableBody.querySelectorAll("[data-summarize-book]").forEach((button) => {
    button.addEventListener("click", async () => {
      const slug = button.getAttribute("data-summarize-book");
      const bookTitle = button.getAttribute("data-book-title") || "";
      if (!slug) return;
      await summarizeBookBySlug(slug, { bookTitle, switchToDetail: false });
    });
  });
}

function extractSection(markdown, sectionName) {
  const pattern = new RegExp(`##\\s+${sectionName}\\n([\\s\\S]*?)(\\n##\\s+|$)`, "m");
  const match = markdown.match(pattern);
  return match ? match[1].trim() : "";
}

function markdownToHtml(markdown) {
  const lines = (markdown || "").split("\n");
  let html = "";
  let inList = false;

  const renderInline = (value) => {
    const escaped = escapeHtml(value);
    return escaped
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  };

  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }

    if (line.startsWith("# ")) {
      closeList();
      html += `<h3>${renderInline(line.slice(2))}</h3>`;
      continue;
    }

    if (line.startsWith("## ")) {
      closeList();
      html += `<h4>${renderInline(line.slice(3))}</h4>`;
      continue;
    }

    if (line.startsWith("### ")) {
      closeList();
      html += `<h5>${renderInline(line.slice(4))}</h5>`;
      continue;
    }

    if (line.startsWith("- ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${renderInline(line.slice(2))}</li>`;
      continue;
    }

    closeList();
    html += `<p>${renderInline(line)}</p>`;
  }

  closeList();
  return html;
}

function clearReaderRuntime() {
  const runtime = state.readerRuntime;
  if (!runtime) return;

  if (runtime.scrollRafId) {
    window.cancelAnimationFrame(runtime.scrollRafId);
  }
  if (runtime.persistTimer) {
    window.clearTimeout(runtime.persistTimer);
  }
  if (runtime.resizeTimer) {
    window.clearTimeout(runtime.resizeTimer);
  }
  if (Array.isArray(runtime.cleanups)) {
    runtime.cleanups.forEach((cleanup) => {
      try {
        cleanup();
      } catch (_error) {
        // noop
      }
    });
  }

  state.readerRuntime = null;
}

function renderReaderBodyHtml(text) {
  const normalized = String(text || "").replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return `<p class="reader-paragraph reader-paragraph-empty">${escapeHtml(t("reader_empty_text"))}</p>`;
  }

  return normalized
    .split(/\n{2,}/)
    .map((paragraph) => `<p class="reader-paragraph">${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function renderReaderPanel(reader, fallbackTitle = "") {
  clearReaderRuntime();

  if (!reader) {
    el.tabReader.innerHTML = `<div class="reader-card"><p class="reader-empty">${escapeHtml(t("reader_loading"))}</p></div>`;
    return;
  }

  if (reader.error) {
    el.tabReader.innerHTML = `<div class="reader-card"><p class="reader-empty">${escapeHtml(reader.error)}</p></div>`;
    return;
  }

  const chapters = Array.isArray(reader.chapters) ? reader.chapters : [];
  if (!chapters.length) {
    const title = reader.book_title || fallbackTitle || "This book";
    el.tabReader.innerHTML = `<div class="reader-card"><p class="reader-empty">${escapeHtml(
      t("reader_no_chapters", { title }),
    )}</p></div>`;
    return;
  }

  const readerSlug =
    (reader.slug || "").trim() || (state.currentBook && typeof state.currentBook.slug === "string" ? state.currentBook.slug : "");
  const flowHtml = chapters
    .map((chapter) => {
      const idx = Number.isFinite(chapter.index) ? chapter.index : "-";
      const title = chapter.title || "Untitled";
      const chapterTitle = escapeHtml(title);
      return `
        <section class="reader-flow-chapter" data-reader-chapter-index="${idx}" data-reader-chapter-title="${chapterTitle}">
          <h3 class="reader-flow-title">${escapeHtml(t("reader_chapter_prefix"))} ${idx}: ${chapterTitle}</h3>
          ${renderReaderBodyHtml(chapter.text || "")}
        </section>
      `;
    })
    .join("");

  el.tabReader.innerHTML = `
    <section class="reader-book">
      <header class="reader-toolbar">
        <button type="button" class="btn btn-ghost reader-nav-btn" data-reader-prev>${escapeHtml(t("pagination_prev"))}</button>
        <div class="reader-toolbar-center">
          <p class="reader-toolbar-chapter" data-reader-current-chapter></p>
          <p class="reader-toolbar-meta">
            <span data-reader-page-info>${escapeHtml(t("page_info", { page: 1, total: 1 }))}</span>
            <span class="reader-toolbar-percent" data-reader-percent>100%</span>
          </p>
        </div>
        <button type="button" class="btn btn-ghost reader-nav-btn" data-reader-next>${escapeHtml(t("pagination_next"))}</button>
      </header>

      <div class="reader-page-wrap">
        <button type="button" class="reader-hotspot reader-hotspot-prev" data-reader-prev aria-label="${escapeHtml(
          t("pagination_prev"),
        )}"></button>
        <div class="reader-page-viewport" data-reader-viewport tabindex="0">
          <article class="reader-flow" data-reader-flow>
            ${flowHtml}
          </article>
        </div>
        <button type="button" class="reader-hotspot reader-hotspot-next" data-reader-next aria-label="${escapeHtml(
          t("pagination_next"),
        )}"></button>
      </div>

      <div class="reader-progress">
        <div class="reader-progress-fill" data-reader-progress-fill></div>
      </div>
      <p class="reader-caption">${escapeHtml(t("reader_progress_saved"))} · ${escapeHtml(t("reader_keyboard_hint"))}</p>
    </section>
  `;

  const viewport = el.tabReader.querySelector("[data-reader-viewport]");
  const flow = el.tabReader.querySelector("[data-reader-flow]");
  const pageInfoNode = el.tabReader.querySelector("[data-reader-page-info]");
  const chapterInfoNode = el.tabReader.querySelector("[data-reader-current-chapter]");
  const percentNode = el.tabReader.querySelector("[data-reader-percent]");
  const progressFill = el.tabReader.querySelector("[data-reader-progress-fill]");
  const prevButtons = Array.from(el.tabReader.querySelectorAll("[data-reader-prev]"));
  const nextButtons = Array.from(el.tabReader.querySelectorAll("[data-reader-next]"));

  if (!viewport || !flow || !pageInfoNode || !chapterInfoNode || !percentNode || !progressFill) {
    return;
  }

  const runtime = {
    slug: readerSlug,
    viewport,
    totalPages: 1,
    currentPage: 0,
    pageStep: 1,
    chapterMarkers: [],
    scrollRafId: 0,
    persistTimer: null,
    resizeTimer: null,
    restored: false,
    cleanups: [],
  };
  state.readerRuntime = runtime;

  const clampPage = (value) => Math.max(0, Math.min(runtime.totalPages - 1, Math.trunc(Number(value) || 0)));

  const updateChapterMarkers = () => {
    const chapterNodes = Array.from(flow.querySelectorAll(".reader-flow-chapter"));
    runtime.chapterMarkers = chapterNodes
      .map((node, order) => {
        const chapterIndex = Number(node.getAttribute("data-reader-chapter-index"));
        const chapterTitle = (node.getAttribute("data-reader-chapter-title") || "").trim() || "Untitled";
        const startLeft = Math.max(0, node.offsetLeft);
        return {
          index: Number.isFinite(chapterIndex) ? chapterIndex : order + 1,
          title: chapterTitle,
          page: clampPage(Math.round(startLeft / runtime.pageStep)),
        };
      })
      .sort((a, b) => a.page - b.page);
  };

  const resolveCurrentChapter = () => {
    if (!runtime.chapterMarkers.length) {
      return { index: 1, title: "Untitled" };
    }
    let selected = runtime.chapterMarkers[0];
    for (const marker of runtime.chapterMarkers) {
      if (marker.page > runtime.currentPage) break;
      selected = marker;
    }
    return selected;
  };

  const renderReaderStatus = () => {
    const safeCurrent = clampPage(runtime.currentPage);
    runtime.currentPage = safeCurrent;

    const chapter = resolveCurrentChapter();
    chapterInfoNode.textContent = `${t("reader_chapter_prefix")} ${chapter.index}: ${chapter.title}`;
    pageInfoNode.textContent = t("page_info", { page: safeCurrent + 1, total: runtime.totalPages });

    const percent =
      runtime.totalPages <= 1 ? 100 : Math.round((safeCurrent / Math.max(1, runtime.totalPages - 1)) * 100);
    percentNode.textContent = `${percent}%`;
    progressFill.style.width = `${percent}%`;

    prevButtons.forEach((button) => {
      button.disabled = safeCurrent <= 0;
    });
    nextButtons.forEach((button) => {
      button.disabled = safeCurrent >= runtime.totalPages - 1;
    });
  };

  const persistCurrentPage = () => {
    if (!runtime.slug) return;
    saveReaderProgress(runtime.slug, runtime.currentPage, runtime.totalPages, { syncServer: true });
  };

  const goToPage = (targetPage, { smooth = true, save = true } = {}) => {
    runtime.currentPage = clampPage(targetPage);
    renderReaderStatus();
    viewport.scrollTo({
      left: runtime.currentPage * runtime.pageStep,
      top: 0,
      behavior: smooth ? "smooth" : "auto",
    });

    if (!save) return;
    if (runtime.persistTimer) {
      window.clearTimeout(runtime.persistTimer);
    }
    if (smooth) {
      runtime.persistTimer = window.setTimeout(() => {
        persistCurrentPage();
        runtime.persistTimer = null;
      }, 220);
      return;
    }

    persistCurrentPage();
  };

  const onScroll = () => {
    if (runtime.scrollRafId) return;

    runtime.scrollRafId = window.requestAnimationFrame(() => {
      runtime.scrollRafId = 0;
      const page = clampPage(Math.round(viewport.scrollLeft / runtime.pageStep));
      if (page !== runtime.currentPage) {
        runtime.currentPage = page;
        renderReaderStatus();
      }

      if (runtime.persistTimer) {
        window.clearTimeout(runtime.persistTimer);
      }
      runtime.persistTimer = window.setTimeout(() => {
        persistCurrentPage();
        runtime.persistTimer = null;
      }, 220);
    });
  };

  const recomputeLayout = () => {
    const previousRatio =
      runtime.totalPages <= 1 ? 0 : runtime.currentPage / Math.max(1, runtime.totalPages - 1);

    const viewportStyle = window.getComputedStyle(viewport);
    const paddingLeft = Number.parseFloat(viewportStyle.paddingLeft);
    const paddingRight = Number.parseFloat(viewportStyle.paddingRight);
    const horizontalPadding =
      (Number.isFinite(paddingLeft) ? paddingLeft : 0) + (Number.isFinite(paddingRight) ? paddingRight : 0);

    // column-width should match the inner readable area, not the padded scroll container width.
    const viewportWidth = Math.max(1, viewport.clientWidth - horizontalPadding);
    viewport.style.setProperty("--reader-page-width", `${viewportWidth}px`);

    const rawGap = viewportStyle.getPropertyValue("--reader-page-gap");
    const pageGap = Number.parseFloat(rawGap);
    runtime.pageStep = Math.max(1, viewportWidth + (Number.isFinite(pageGap) ? pageGap : 40));

    const maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
    runtime.totalPages = Math.max(1, Math.floor(maxScroll / runtime.pageStep) + 1);
    updateChapterMarkers();

    runtime.currentPage = runtime.restored
      ? clampPage(Math.round(previousRatio * Math.max(0, runtime.totalPages - 1)))
      : clampPage(resolveSavedReaderPage(runtime.slug, runtime.totalPages));
    runtime.restored = true;

    renderReaderStatus();
    viewport.scrollTo({ left: runtime.currentPage * runtime.pageStep, top: 0, behavior: "auto" });
    persistCurrentPage();
  };

  const onResize = () => {
    if (runtime.resizeTimer) {
      window.clearTimeout(runtime.resizeTimer);
    }
    runtime.resizeTimer = window.setTimeout(() => {
      recomputeLayout();
      runtime.resizeTimer = null;
    }, 140);
  };

  const onKeydown = (event) => {
    if (state.currentView !== "detail" || state.currentTab !== "reader") return;
    if (!state.currentBook || state.currentBook.slug !== runtime.slug) return;

    const target = event.target;
    const tagName = target && typeof target.tagName === "string" ? target.tagName.toLowerCase() : "";
    if (target && target.isContentEditable) return;
    if (tagName === "input" || tagName === "textarea" || tagName === "select") return;

    if (event.key === "ArrowRight" || event.key === "PageDown") {
      event.preventDefault();
      goToPage(runtime.currentPage + 1);
      return;
    }

    if (event.key === "ArrowLeft" || event.key === "PageUp") {
      event.preventDefault();
      goToPage(runtime.currentPage - 1);
    }
  };

  prevButtons.forEach((button) => {
    button.addEventListener("click", () => goToPage(runtime.currentPage - 1));
  });
  nextButtons.forEach((button) => {
    button.addEventListener("click", () => goToPage(runtime.currentPage + 1));
  });
  viewport.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onResize);
  document.addEventListener("keydown", onKeydown);

  runtime.cleanups.push(() => viewport.removeEventListener("scroll", onScroll));
  runtime.cleanups.push(() => window.removeEventListener("resize", onResize));
  runtime.cleanups.push(() => document.removeEventListener("keydown", onKeydown));

  window.requestAnimationFrame(() => {
    if (state.readerRuntime !== runtime) return;
    recomputeLayout();
  });
}

async function loadReaderForBook(slug, fallbackTitle = "", { force = false, syncProgress = true } = {}) {
  if (!slug) return;
  if (syncProgress) {
    await loadReaderProgressFromServer(slug, { force });
  }

  const cached = state.readerCache[slug];
  if (cached && !force) {
    renderReaderPanel(cached, fallbackTitle);
    return;
  }

  const reqId = ++state.readerRequestSeq;
  renderReaderPanel(null, fallbackTitle);

  try {
    const payload = await fetchJson(`/books/${encodeURIComponent(slug)}/reader`);
    state.readerCache[slug] = payload;
    if (reqId !== state.readerRequestSeq) return;
    if (!state.currentBook || state.currentBook.slug !== slug) return;
    renderReaderPanel(payload, fallbackTitle);
  } catch (error) {
    const fallback = {
      slug,
      book_title: fallbackTitle || "",
      chapter_count: 0,
      chapters: [],
      error: error.message || t("reader_load_failed"),
    };
    state.readerCache[slug] = fallback;
    if (reqId !== state.readerRequestSeq) return;
    if (!state.currentBook || state.currentBook.slug !== slug) return;
    renderReaderPanel(fallback, fallbackTitle);
  }
}

function renderAskCharacterOptions(detail) {
  if (!el.askCharacterSelect) return;

  const selected = (el.askCharacterSelect.value || "").trim();
  const names = [];
  const seen = new Set();

  for (const character of detail.characters || []) {
    const name = (character?.name || "").trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    names.push(name);
  }

  const optionsHtml = [
    `<option value="">${escapeHtml(t("ask_character_select_placeholder"))}</option>`,
    ...names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`),
  ].join("");

  el.askCharacterSelect.innerHTML = optionsHtml;
  el.askCharacterSelect.disabled = names.length === 0;

  if (selected && names.includes(selected)) {
    el.askCharacterSelect.value = selected;
  }
}

function renderDetail(detail) {
  el.detailTitle.textContent = detail.book_title;
  el.detailSubtitle.textContent = `slug: ${detail.slug}`;
  el.detailChapterCount.textContent = String(detail.chapter_count);
  el.detailCharacterCount.textContent = String(detail.character_count);
  el.detailUpdatedAt.textContent = formatDate(detail.updated_at);

  el.insightBookTitle.textContent = detail.book_title;
  el.insightBookStats.textContent = t("insight_stats", {
    chapters: detail.chapter_count,
    characters: detail.character_count,
  });

  if (!detail.chapters.length) {
    el.tabChapter.innerHTML = `<div class="chapter-card"><p class="chapter-snippet">${escapeHtml(
      t("empty_chapter_summary"),
    )}</p></div>`;
  } else {
    el.tabChapter.innerHTML = detail.chapters
      .map((chapter) => {
        const summary = extractSection(chapter.markdown, "요약") || t("summary_text_missing");
        return `
          <article class="chapter-card">
            <h3 class="chapter-title">${escapeHtml(t("reader_chapter_prefix"))} ${chapter.index}: ${escapeHtml(chapter.title)}</h3>
            <p class="chapter-snippet">${escapeHtml(summary)}</p>
            <details>
              <summary>${escapeHtml(t("view_original"))} (${escapeHtml(chapter.file_name)})</summary>
              <div class="markdown-view markdown-inline">${markdownToHtml(chapter.markdown)}</div>
            </details>
          </article>
        `;
      })
      .join("");
  }

  if (!detail.characters.length) {
    el.tabCharacter.innerHTML = `<div class="character-card"><p class="character-snippet">${escapeHtml(
      t("empty_character_summary"),
    )}</p></div>`;
  } else {
    el.tabCharacter.innerHTML = detail.characters
      .map((character) => {
        const preview = character.markdown.split("\n").slice(0, 6).join("\n");
        return `
          <article class="character-card">
            <h3 class="character-title">${escapeHtml(character.name)}</h3>
            <p class="character-snippet">${escapeHtml(preview).replaceAll("\n", "<br>")}</p>
            <details>
              <summary>${escapeHtml(t("view_original"))} (${escapeHtml(character.file_name)})</summary>
              <div class="markdown-view markdown-inline">${markdownToHtml(character.markdown)}</div>
            </details>
          </article>
        `;
      })
      .join("");
  }

  el.tabWorld.innerHTML = `<div class="markdown-view">${markdownToHtml(detail.setting_markdown || t("world_missing"))}</div>`;
  renderAskCharacterOptions(detail);
  renderReaderPanel(state.readerCache[detail.slug] || null, detail.book_title);
  void loadChatScript(detail.slug, detail.book_title);
  if (el.askBookAnswer) el.askBookAnswer.textContent = t("ask_empty");
  if (el.askCharacterAnswer) el.askCharacterAnswer.textContent = t("ask_empty");

  setTab(state.currentTab);
}

function setTab(tabName) {
  state.currentTab = tabName;
  el.tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  el.tabChapter?.classList.toggle("active", tabName === "chapter");
  el.tabCharacter?.classList.toggle("active", tabName === "character");
  el.tabWorld?.classList.toggle("active", tabName === "world");
  el.tabReader?.classList.toggle("active", tabName === "reader");
  el.tabChat?.classList.toggle("active", tabName === "chat");
  el.tabAskBook?.classList.toggle("active", tabName === "ask-book");
  el.tabAskCharacter?.classList.toggle("active", tabName === "ask-character");
}

const CHAT_NARRATOR_ALIASES = new Set(["narrator", "내레이터", "나레이터", "해설자"]);

function isNarratorSpeaker(speaker) {
  const normalized = (speaker || "").trim().toLowerCase();
  return !normalized || CHAT_NARRATOR_ALIASES.has(normalized);
}

function chatBubbleSide(speakerSides, speaker) {
  if (!speakerSides.has(speaker)) {
    const sides = Array.from(speakerSides.values());
    const rightCount = sides.filter((side) => side === "right").length;
    const leftCount = sides.length - rightCount;
    speakerSides.set(speaker, rightCount <= leftCount ? "right" : "left");
  }
  return speakerSides.get(speaker);
}

function renderChatEmptyState(message) {
  el.tabChat.innerHTML = `
    <div class="chat-card">
      <p class="chat-empty">${escapeHtml(message)}</p>
      <button type="button" class="btn btn-primary" data-chat-generate>${escapeHtml(t("chat_generate_btn"))}</button>
    </div>
  `;
  el.tabChat.querySelector("[data-chat-generate]")?.addEventListener("click", () => void generateChatScript());
}

function renderChatPanel(script, fallbackTitle = "") {
  if (!script) {
    el.tabChat.innerHTML = `<div class="chat-card"><p class="chat-empty">${escapeHtml(t("chat_loading"))}</p></div>`;
    return;
  }

  const chapters = Array.isArray(script.chapters) ? script.chapters : [];
  if (script.error || !chapters.length) {
    renderChatEmptyState(script.error || t("chat_empty"));
    return;
  }

  const speakerSides = new Map();
  const chaptersHtml = chapters
    .map((chapter) => {
      const linesHtml = (chapter.lines || [])
        .map((line) => {
          const speaker = (line.speaker || "narrator").trim() || "narrator";
          const text = escapeHtml(line.text || "");
          if (isNarratorSpeaker(speaker)) {
            return `<p class="chat-narration">${text}</p>`;
          }
          const side = chatBubbleSide(speakerSides, speaker);
          return `
            <div class="chat-row chat-row-${side}">
              <span class="chat-speaker">${escapeHtml(speaker)}</span>
              <div class="chat-bubble chat-bubble-${side}">${text}</div>
            </div>
          `;
        })
        .join("");
      return `
        <section class="chat-chapter">
          <h3 class="chat-chapter-title">${escapeHtml(t("reader_chapter_prefix"))} ${chapter.chapter_index}: ${escapeHtml(
            chapter.chapter_title || "",
          )}</h3>
          ${linesHtml}
        </section>
      `;
    })
    .join("");

  el.tabChat.innerHTML = `
    <div class="chat-card">
      <header class="chat-toolbar">
        <button type="button" class="btn btn-ghost" data-chat-generate>${escapeHtml(t("chat_regenerate_btn"))}</button>
      </header>
      <div class="chat-scroll">${chaptersHtml}</div>
    </div>
  `;
  el.tabChat.querySelector("[data-chat-generate]")?.addEventListener("click", () => void generateChatScript());
}

async function loadChatScript(slug, fallbackTitle = "", { force = false } = {}) {
  if (!slug || !el.tabChat) return;
  if (!force && state.chatCache && state.chatCache.slug === slug) {
    renderChatPanel(state.chatCache.data, fallbackTitle);
    return;
  }

  renderChatPanel(null, fallbackTitle);
  try {
    const payload = await fetchJson(`/books/${encodeURIComponent(slug)}/chat-script`);
    if (!state.currentBook || state.currentBook.slug !== slug) return;
    state.chatCache = { slug, data: payload };
    renderChatPanel(payload, fallbackTitle);
  } catch (error) {
    if (!state.currentBook || state.currentBook.slug !== slug) return;
    state.chatCache = { slug, data: { error: t("chat_empty"), chapters: [] } };
    renderChatPanel(state.chatCache.data, fallbackTitle);
  }
}

async function generateChatScript() {
  const detail = state.currentBook;
  if (!detail || !detail.slug) {
    showToast(t("select_book_first"), true);
    return;
  }

  const button = el.tabChat.querySelector("[data-chat-generate]");
  if (button) button.disabled = true;
  showToast(t("chat_generating"));

  try {
    const config = getRunConfig();
    const payload = await fetchJson(`/books/${encodeURIComponent(detail.slug)}/chat-script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: config.provider,
        model: config.model,
        api_key: config.apiKey,
        language: config.language,
      }),
    });
    state.chatCache = { slug: detail.slug, data: payload };
    renderChatPanel(payload, detail.book_title);
    showToast(t("chat_generate_done"));
  } catch (error) {
    showToast(error.message || t("chat_generate_failed"), true);
    if (button) button.disabled = false;
  }
}

async function openBook(slug, { switchToDetail = false } = {}) {
  const detail = await fetchJson(`/books/${encodeURIComponent(slug)}`);
  state.currentBook = detail;
  await loadReaderProgressFromServer(detail.slug, { force: true });
  renderDetail(detail);
  void loadReaderForBook(detail.slug, detail.book_title, { force: true, syncProgress: false });

  if (switchToDetail) {
    switchView("detail");
  }
}

function openFilePicker(mode) {
  state.pendingUploadMode = mode;
  el.fileInput.multiple = mode === "multi";
  el.fileInput.value = "";
  el.fileInput.click();
}

function getRunConfig() {
  syncSettingsFromForm();

  const provider = state.settings.selectedProvider;
  const model = state.settings.models[provider] || DEFAULT_MODEL_BY_PROVIDER[provider] || "";
  const apiKey = state.settings.apiKeys[provider] || "";
  const language = state.settings.language || "ko";
  const uploadParallel = clampUploadParallel(state.settings.uploadParallel);
  const preciseAnalysis = Boolean(state.settings.preciseAnalysis);
  return { provider, model, apiKey, language, uploadParallel, preciseAnalysis };
}

function appendRunConfigToFormData(formData, config) {
  formData.append("provider", config.provider);
  formData.append("language", config.language);
  formData.append("precise_analysis", String(Boolean(config.preciseAnalysis)));
  formData.append("chapter_parallel", String(clampUploadParallel(config.uploadParallel)));
  if (config.model) formData.append("model", config.model);
  if (config.apiKey) formData.append("api_key", config.apiKey);
}

function buildSingleUploadFormData(file, config) {
  const formData = new FormData();
  formData.append("file", file);
  if (config.uploadId) formData.append("upload_id", config.uploadId);
  appendRunConfigToFormData(formData, config);
  return formData;
}

function buildSummarizeBookFormData(config, uploadId = "") {
  const formData = new FormData();
  if (uploadId) formData.append("upload_id", uploadId);
  appendRunConfigToFormData(formData, config);
  return formData;
}

function scheduleCompletedCleanup(pendingRow) {
  if (pendingRow.completionTimerId) return;
  const completionTimerId = window.setTimeout(async () => {
    removePendingUpload(pendingRow.id);
    try {
      await loadLibrary({ autoOpenFirst: false });
    } catch (_error) {
      // 라이브러리 갱신 실패는 다음 갱신에서 복구된다.
    }
  }, 1200);
  updatePendingUpload(pendingRow.id, { completionTimerId });
}

function startProgressPolling(pendingRow) {
  if (pendingRow.timerId) {
    return () => {};
  }

  let stopped = false;
  let timerId = null;

  const stop = () => {
    stopped = true;
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }
    updatePendingUpload(pendingRow.id, { timerId: null });
  };

  const poll = async () => {
    if (stopped) return;
    try {
      const payload = await fetchJson(`/uploads/${encodeURIComponent(pendingRow.uploadId)}/progress`);
      const patch = {
        status: payload.status || "processing",
        progress: Number.isFinite(payload.progress) ? payload.progress : 0,
        message: payload.message || "",
        stage: payload.stage || "processing",
        error: payload.error || "",
        chapterIndex: payload.chapter_index ?? null,
        chapterTotal: payload.chapter_total ?? null,
        chapterTitle: payload.chapter_title || "",
        characterIndex: payload.character_index ?? null,
        characterTotal: payload.character_total ?? null,
        characterName: payload.character_name || "",
      };

      if (typeof payload.book_title === "string" && payload.book_title.trim()) {
        patch.bookTitle = payload.book_title.trim();
        patch.displayName = payload.book_title.trim();
      }

      updatePendingUpload(pendingRow.id, patch);

      if (payload.status === "completed") {
        stop();
        scheduleCompletedCleanup(pendingRow);
        return;
      }
      if (payload.status === "failed") {
        stop();
      }
    } catch (_error) {
      // Upload 시작 직후에는 progress 레코드가 아직 없을 수 있어 다음 폴링에서 재시도한다.
    }
  };

  timerId = window.setInterval(() => {
    void poll();
  }, 800);
  updatePendingUpload(pendingRow.id, { timerId });
  void poll();

  return stop;
}

async function uploadSingleFile(file, config, pendingRow) {
  updatePendingUpload(pendingRow.id, {
    status: "processing",
    progress: 1,
    message: t("upload_start"),
    error: "",
  });
  const stopPolling = startProgressPolling(pendingRow);

  try {
    const formData = buildSingleUploadFormData(file, { ...config, uploadId: pendingRow.uploadId });
    const payload = await fetchJson("/summaries/from-epub", {
      method: "POST",
      body: formData,
    });

    stopPolling();
    updatePendingUpload(pendingRow.id, {
      status: "completed",
      progress: 100,
      stage: "done",
      message: t("summary_done"),
      timerId: null,
    });
    scheduleCompletedCleanup(pendingRow);
    return { ok: true, payload };
  } catch (error) {
    stopPolling();
    updatePendingUpload(pendingRow.id, {
      status: "failed",
      progress: 100,
      stage: "failed",
      message: t("summary_failed"),
      error: error.message || t("summary_failed"),
      timerId: null,
    });
    return { ok: false, error };
  }
}

async function uploadSingleFileOnly(file, pendingRow) {
  updatePendingUpload(pendingRow.id, {
    status: "processing",
    progress: 10,
    stage: "upload",
    message: t("upload_start"),
    error: "",
  });

  try {
    const formData = new FormData();
    formData.append("file", file);
    const payload = await fetchJson("/books/upload-epub", {
      method: "POST",
      body: formData,
    });
    updatePendingUpload(pendingRow.id, {
      status: "completed",
      progress: 100,
      stage: "done",
      message: t("upload_saved"),
      bookTitle: payload.book_title || pendingRow.bookTitle || file.name,
      displayName: payload.book_title || pendingRow.displayName || file.name,
      timerId: null,
    });
    scheduleCompletedCleanup(pendingRow);
    return { ok: true, payload };
  } catch (error) {
    updatePendingUpload(pendingRow.id, {
      status: "failed",
      progress: 100,
      stage: "failed",
      message: t("upload_error"),
      error: error.message || t("upload_error"),
      timerId: null,
    });
    return { ok: false, error };
  }
}

async function summarizeBookBySlug(slug, { bookTitle = "", switchToDetail = true } = {}) {
  if (!slug) return;

  let config;
  try {
    config = getRunConfig();
  } catch (error) {
    showToast(error.message || t("config_error"), true);
    return;
  }

  const pendingRow = addPendingUpload(`${bookTitle || slug}.epub`, {
    status: "processing",
    progress: 1,
    stage: "start",
    message: t("stage_start"),
    bookTitle: bookTitle || slug,
    displayName: bookTitle || slug,
  });

  const stopPolling = startProgressPolling(pendingRow);
  try {
    const formData = buildSummarizeBookFormData(config, pendingRow.uploadId);
    const payload = await fetchJson(`/books/${encodeURIComponent(slug)}/summaries`, {
      method: "POST",
      body: formData,
    });

    stopPolling();
    updatePendingUpload(pendingRow.id, {
      status: "completed",
      progress: 100,
      stage: "done",
      message: t("summary_done"),
      timerId: null,
    });
    scheduleCompletedCleanup(pendingRow);

    if (switchToDetail) {
      await openBook(slug, { switchToDetail: true });
    }
    return payload;
  } catch (error) {
    stopPolling();
    updatePendingUpload(pendingRow.id, {
      status: "failed",
      progress: 100,
      stage: "failed",
      message: t("summary_failed"),
      error: error.message || t("summary_failed"),
      timerId: null,
    });
    showToast(error.message || t("summary_failed"), true);
    return null;
  }
}

async function runWithConcurrency(items, limit, worker) {
  const size = Math.max(1, Math.min(limit, items.length || 1));
  const results = new Array(items.length);
  let cursor = 0;

  async function runner() {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= items.length) {
        return;
      }
      results[index] = await worker(items[index], index);
    }
  }

  const workers = Array.from({ length: size }, () => runner());
  await Promise.all(workers);
  return results;
}

async function uploadFiles(files) {
  if (!files.length) return;

  syncSettingsFromForm();
  const autoSummarizeOnUpload = Boolean(state.settings.autoSummarizeOnUpload);
  let config = null;
  if (autoSummarizeOnUpload) {
    try {
      config = getRunConfig();
    } catch (error) {
      showToast(error.message || t("config_error"), true);
      return;
    }
  }

  const pendingRows = files.map((file) => addPendingUpload(file.name));

  let successCount = 0;
  let failureCount = 0;
  let firstErrorMessage = "";

  try {
    setUploading(true);

    const results = await runWithConcurrency(
      files,
      Math.min(
        clampUploadParallel(autoSummarizeOnUpload ? config.uploadParallel : state.settings.uploadParallel),
        files.length,
      ),
      async (file, index) =>
        autoSummarizeOnUpload
          ? uploadSingleFile(file, config, pendingRows[index])
          : uploadSingleFileOnly(file, pendingRows[index]),
    );

    for (const result of results) {
      if (result.ok) {
        successCount += 1;
      } else {
        failureCount += 1;
        if (!firstErrorMessage) {
          firstErrorMessage = result.error?.message || t("summary_failed");
        }
      }
    }

    if (successCount > 0) {
      await loadLibrary({ autoOpenFirst: false });
    }

    const summaryMessage =
      autoSummarizeOnUpload
        ? failureCount > 0 && firstErrorMessage
          ? t("result_with_error", { success: successCount, failure: failureCount, error: firstErrorMessage })
          : t("result_summary", { success: successCount, failure: failureCount })
        : t("result_upload_only", { success: successCount, failure: failureCount });
    showToast(summaryMessage, failureCount > 0);
    if (successCount > 0) switchView("library");
  } catch (error) {
    showToast(error.message || t("upload_error"), true);
  } finally {
    setUploading(false);
  }
}

async function restoreActiveUploads() {
  let payload;
  try {
    payload = await fetchJson("/uploads/active");
  } catch (_error) {
    return;
  }

  if (!Array.isArray(payload) || payload.length === 0) {
    return;
  }

  for (const row of payload) {
    if (!row || typeof row !== "object") continue;
    const uploadId = typeof row.upload_id === "string" ? row.upload_id.trim() : "";
    if (!uploadId) continue;

    const status = typeof row.status === "string" ? row.status : "queued";
    if (status !== "queued" && status !== "processing") continue;

    const fileName =
      typeof row.file_name === "string" && row.file_name.trim() ? row.file_name.trim() : "unknown.epub";
    const bookTitle =
      typeof row.book_title === "string" && row.book_title.trim() ? row.book_title.trim() : "";
    const options = {
      uploadId,
      status,
      progress: Number.isFinite(row.progress) ? row.progress : 0,
      message: row.message || "",
      stage: row.stage || "queued",
      error: row.error || "",
      bookTitle,
      displayName: bookTitle || fileName,
      chapterIndex: row.chapter_index ?? null,
      chapterTotal: row.chapter_total ?? null,
      chapterTitle: row.chapter_title || "",
      characterIndex: row.character_index ?? null,
      characterTotal: row.character_total ?? null,
      characterName: row.character_name || "",
    };

    const existing = findPendingUploadByUploadId(uploadId);
    if (existing) {
      updatePendingUpload(existing.id, options);
      startProgressPolling(existing);
      continue;
    }

    const pendingRow = addPendingUpload(fileName, options);
    startProgressPolling(pendingRow);
  }
}

function bindSettingsEvents() {
  el.settingsProviderSelect?.addEventListener("change", () => {
    syncSettingsFromForm();
    void fetchProviderModels(state.settings.selectedProvider, { force: true, silent: false });
  });

  el.settingsModelSelect?.addEventListener("change", () => {
    if (el.settingsModelSelect.value === CUSTOM_MODEL_VALUE) {
      setCustomModelVisible(true);
      el.settingsCustomModelInput?.focus();
      return;
    }
    setCustomModelVisible(false);
    syncSettingsFromForm();
  });

  el.settingsCustomModelInput?.addEventListener("change", () => {
    syncSettingsFromForm();
  });

  el.settingsUiLanguageInput?.addEventListener("change", () => {
    syncSettingsFromForm();
    renderBooksTable(state.items);
    if (state.currentBook) {
      renderDetail(state.currentBook);
    }
    loadLibrary({ autoOpenFirst: false }).catch(() => {});
  });

  el.settingsLanguageInput?.addEventListener("change", () => {
    syncSettingsFromForm();
  });

  el.settingsUploadParallelInput?.addEventListener("change", () => {
    syncSettingsFromForm();
  });

  el.settingsPreciseAnalysisInput?.addEventListener("change", () => {
    syncSettingsFromForm();
  });

  el.settingsAutoSummarizeInput?.addEventListener("change", () => {
    syncSettingsFromForm();
  });

  [
    { element: el.apiKeyOpenAi, provider: "open-ai" },
    { element: el.apiKeyAnthropic, provider: "anthropic" },
    { element: el.apiKeyOpenrouter, provider: "openrouter" },
    { element: el.apiKeyVenice, provider: "venice" },
    { element: el.apiKeyKiloCode, provider: "kilo-code" },
    { element: el.apiKeyOpencodeGo, provider: "opencode-go" },
    { element: el.apiKeyOpencodeZen, provider: "opencode-zen" },
  ].forEach(({ element, provider }) => {
    if (!element) return;
    element.addEventListener("change", () => {
      syncSettingsFromForm();
      if (state.currentView === "settings") {
        void fetchProviderModels(provider, { force: true, silent: true });
      }
    });
  });

  el.settingsSaveBtn?.addEventListener("click", async () => {
    syncSettingsFromForm();
    await fetchProviderModels(state.settings.selectedProvider, { force: true, silent: true });
    showToast(t("settings_saved"));
  });
}

function bindEvents() {
  el.navLibrary.addEventListener("click", () => switchView("library"));

  if (el.navDetail) {
    el.navDetail.addEventListener("click", () => {
      if (!state.currentBook) {
        showToast(t("select_book_first"), true);
        return;
      }
      switchView("detail");
    });
  }

  el.navSettings.addEventListener("click", () => {
    switchView("settings");
  });

  el.uploadBooksBtn.addEventListener("click", () => openFilePicker("multi"));
  el.uploadSingleBtn.addEventListener("click", () => openFilePicker("single"));
  el.generateFromDetailBtn.addEventListener("click", () => {
    if (!state.currentBook || !state.currentBook.slug) {
      showToast(t("select_book_first"), true);
      return;
    }
    void summarizeBookBySlug(state.currentBook.slug, {
      bookTitle: state.currentBook.book_title || "",
      switchToDetail: true,
    });
  });
  el.askBookSubmitBtn?.addEventListener("click", () => {
    void submitAsk({
      mode: "book",
      questionInput: el.askBookQuestionInput,
      submitBtn: el.askBookSubmitBtn,
      answerBox: el.askBookAnswer,
    });
  });
  el.askCharacterSubmitBtn?.addEventListener("click", () => {
    void submitAsk({
      mode: "character",
      questionInput: el.askCharacterQuestionInput,
      characterSelect: el.askCharacterSelect,
      submitBtn: el.askCharacterSubmitBtn,
      answerBox: el.askCharacterAnswer,
    });
  });

  el.fileInput.addEventListener("change", async () => {
    const files = Array.from(el.fileInput.files || []);
    if (!files.length) return;
    const picked = state.pendingUploadMode === "single" ? files.slice(0, 1) : files;
    await uploadFiles(picked);
  });

  el.prevPageBtn.addEventListener("click", async () => {
    if (state.page <= 1) return;
    state.page -= 1;
    await loadLibrary();
  });

  el.nextPageBtn.addEventListener("click", async () => {
    if (state.page >= currentPageCount()) return;
    state.page += 1;
    await loadLibrary();
  });

  el.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.tab));
  });

  bindSettingsEvents();
}

async function init() {
  initializeModelOptionState();
  loadSettingsFromStorage();
  loadReaderProgressFromStorage();
  bindEvents();
  setTab("chapter");
  await fetchProviderModels(state.settings.selectedProvider, { force: true, silent: true });
  await restoreActiveUploads();

  try {
    await loadLibrary();
    if (state.items.length > 0) {
      await openBook(state.items[0].slug);
    }
  } catch (error) {
    showToast(error.message || t("init_load_failed"), true);
  }
}

void init();


async function submitAsk({ mode = "book", questionInput, characterSelect = null, submitBtn, answerBox }) {
  if (!questionInput || !submitBtn || !answerBox) {
    return;
  }

  const detail = state.currentBook;
  if (!detail || !detail.slug) {
    showToast(t("select_book_first"), true);
    return;
  }

  const askMode = mode.trim() === "character" ? "character" : "book";
  const question = (questionInput.value || "").trim();
  const characterName = (characterSelect?.value || "").trim();

  if (!question) {
    showToast(t("ask_need_question"), true);
    return;
  }
  if (askMode === "character" && !characterName) {
    showToast(t("ask_need_character"), true);
    return;
  }

  answerBox.textContent = t("ask_loading");
  submitBtn.disabled = true;
  try {
    const config = getRunConfig();
    const response = await fetch(`/books/${encodeURIComponent(detail.slug)}/ask/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        mode: askMode,
        character_name: askMode === "character" ? characterName : null,
        provider: config.provider,
        model: config.model,
        api_key: config.apiKey,
        language: config.language,
      }),
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      const contentType = (response.headers.get("content-type") || "").toLowerCase();
      if (contentType.includes("application/json")) {
        const payload = await response.json().catch(() => null);
        message = payload?.detail || message;
      } else {
        const text = (await response.text().catch(() => "")).trim();
        if (text) message = text;
      }
      throw new Error(message);
    }

    if (!response.body) {
      const text = await response.text();
      answerBox.innerHTML = `<div class="markdown-view markdown-inline">${markdownToHtml(
        (text || "").trim() || t("summary_text_missing"),
      )}</div>`;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let streamed = "";
    answerBox.textContent = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      streamed += decoder.decode(value, { stream: true });
      answerBox.textContent = streamed;
    }
    streamed += decoder.decode();

    answerBox.innerHTML = `<div class="markdown-view markdown-inline">${markdownToHtml(
      streamed.trim() ? streamed : t("summary_text_missing"),
    )}</div>`;
  } catch (error) {
    answerBox.textContent = error.message || "Error";
  } finally {
    submitBtn.disabled = false;
  }
}
