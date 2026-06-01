// ═══════════════════════════════════════════
// data.jsx — static UI constants (role colors)
// ═══════════════════════════════════════════

const ROLE_COLOR = {
  Brain:   { c: 'var(--accent-2)',  bg: 'var(--accent-2-dim)' },
  Power:   { c: 'var(--accent)',    bg: 'var(--accent-dim)' },
  Control: { c: 'var(--green)',     bg: 'var(--green-dim)' },
  Sensor:  { c: 'var(--accent-2)',  bg: 'var(--accent-2-dim)' },
  Output:  { c: 'var(--purple)',    bg: 'rgba(180,130,255,0.12)' },
  Housing: { c: 'var(--text-secondary)', bg: 'var(--bg-hover)' },
  Comm:    { c: 'var(--accent)',    bg: 'var(--accent-dim)' },
  Actuator:{ c: 'var(--purple)',    bg: 'rgba(180,130,255,0.12)' },
  Lighting:{ c: 'var(--accent)',    bg: 'var(--accent-dim)' },
  Display: { c: 'var(--accent)',    bg: 'var(--accent-dim)' },
  Audio:   { c: 'var(--purple)',    bg: 'rgba(180,130,255,0.12)' },
  Motor:   { c: 'var(--purple)',    bg: 'rgba(180,130,255,0.12)' },
  Sound:   { c: 'var(--purple)',    bg: 'rgba(180,130,255,0.12)' },
};

// ═══════════════════════════════════════════
// CHALLENGE_CATALOG — Engage 階段 Category Explorer 資料
// tag 名稱與 assembly_solver step 名稱對齊
// ═══════════════════════════════════════════
const CHALLENGE_CATALOG = {
  Gardening: {
    label: '智慧園藝', icon: '🌱',
    templates: [
      { name: '自動澆花器', prompt: '智慧花盆 自動澆水系統',
        canned_bridge: 'auto_waterer',
        difficulty: 2, components: 4,
        challenges: [
          { tag: 'thermal', icon: '🔥', label: '熱管理',
            preview: '水泵持續運轉 2W，殼內溫升需通風柵散熱' },
          { tag: 'high_current', icon: '⚡', label: '大電流驅動',
            preview: '水泵 400mA 超過 GPIO 20mA 上限，需繼電器隔離' },
          { tag: 'waterproof', icon: '💧', label: '防水設計',
            preview: '土壤探針穿出殼體，需考慮密封處理' },
        ]},
      { name: '植物監測儀', prompt: '植物監測儀',
        canned_bridge: 'plant_monitor',
        difficulty: 1, components: 3,
        challenges: [
          { tag: 'low_power', icon: '🔋', label: '低功耗',
            preview: '電池供電需最佳化 sleep 週期延長續航' },
          { tag: 'i2c', icon: '🔌', label: 'I2C 匯流排',
            preview: 'OLED + 感測器共用 I2C，需注意位址衝突' },
        ]},
    ],
  },
  Smart_Home: {
    label: '智慧家居', icon: '🏠',
    templates: [
      { name: '智慧小夜燈', prompt: '智慧小夜燈',
        canned_bridge: 'smart_nightlight',
        difficulty: 1, components: 3,
        challenges: [
          { tag: 'low_power', icon: '🔋', label: '低功耗',
            preview: '夜間常亮需控制 LED 電流，避免過熱' },
          { tag: 'port_orient', icon: '👁️', label: '感測方向',
            preview: '光敏電阻需朝外殼開口，確保偵測環境光' },
        ]},
      { name: '自動窗簾', prompt: '自動窗簾',
        canned_bridge: 'auto_curtain',
        difficulty: 3, components: 5,
        scope: 'layer4', scope_note: '步進馬達 + 結構受力屬 Layer 4 多軸機構',
        challenges: [
          { tag: 'high_current', icon: '⚡', label: '馬達驅動',
            preview: '步進馬達啟動電流 800mA，需獨立電源' },
          { tag: 'structural', icon: '🔩', label: '結構強度',
            preview: '馬達扭力反作用於殼體，需加強固定座' },
          { tag: 'cable_routing', icon: '🔗', label: '線路管理',
            preview: '電源線與訊號線需分離，降低 EMI 干擾' },
        ]},
      { name: '語音門鈴', prompt: '語音門鈴',
        canned_bridge: 'voice_doorbell',
        difficulty: 2, components: 4,
        challenges: [
          { tag: 'port_orient', icon: '🔊', label: '音訊輸出',
            preview: '喇叭開孔需朝向使用者，影響殼體佈局' },
          { tag: 'thermal', icon: '🔥', label: '功耗管理',
            preview: 'DFPlayer + 喇叭播放峰值 1W，需散熱考量' },
        ]},
    ],
  },
  Robotics: {
    label: '機器人', icon: '🤖',
    templates: [
      { name: '遙控車', prompt: '遙控車',
        canned_bridge: 'rc_car',
        difficulty: 3, components: 6,
        challenges: [
          { tag: 'high_current', icon: '⚡', label: '雙馬達驅動',
            preview: '兩顆 DC 馬達同時運轉，總電流可達 1.5A' },
          { tag: 'gravity_sort', icon: '⚖️', label: '重心平衡',
            preview: '電池（最重）需放底部中央，避免翻車' },
          { tag: 'cable_routing', icon: '🔗', label: '走線空間',
            preview: '馬達線 + 感測器線 + 電源線需有序佈線' },
        ]},
      { name: '避障車', prompt: '避障車',
        canned_bridge: 'obstacle_car',
        difficulty: 2, components: 5,
        challenges: [
          { tag: 'port_orient', icon: '👁️', label: '感測方向',
            preview: '超音波模組需面朝前方，影響殼體開孔位置' },
          { tag: 'high_current', icon: '⚡', label: '馬達驅動',
            preview: 'DC 馬達經 L298N 驅動，需獨立電源' },
        ]},
      { name: '說話機器人', prompt: '說話機器人',
        canned_bridge: 'talking_robot',
        difficulty: 2, components: 5,
        challenges: [
          { tag: 'port_orient', icon: '🔊', label: '音訊方向',
            preview: '喇叭 + PIR 需各朝不同方向，殼體多面開孔' },
          { tag: 'i2c', icon: '🔌', label: '匯流排管理',
            preview: 'OLED 顯示 + 感測器共用 I2C，需確認位址' },
        ]},
    ],
  },
  Interactive_Art: {
    label: '互動藝術', icon: '🎨',
    templates: [
      { name: '音樂盒', prompt: '音樂盒',
        canned_bridge: 'music_box',
        difficulty: 2, components: 4,
        challenges: [
          { tag: 'port_orient', icon: '🔊', label: '音訊擴散',
            preview: '喇叭朝上開孔，蓋子設計需保留聲音通道' },
          { tag: 'structural', icon: '🔩', label: '開蓋機構',
            preview: '翻蓋觸發開關，需設計鉸鏈 + 微動開關' },
        ]},
      { name: '光劍', prompt: '光劍',
        canned_bridge: 'lightsaber',
        difficulty: 3, components: 5,
        scope: 'layer4', scope_note: '2A 高電流 + 長條結構受力屬 Layer 4 進階',
        challenges: [
          { tag: 'high_current', icon: '⚡', label: 'LED 驅動',
            preview: 'WS2812B 燈條全亮 2A，需大容量鋰電池' },
          { tag: 'structural', icon: '🔩', label: '線性結構',
            preview: '長條形殼體需承受揮動衝擊，壁厚 + 卡扣強化' },
          { tag: 'thermal', icon: '🔥', label: 'LED 散熱',
            preview: '全亮模式 10W，需沿管身設計散熱通道' },
        ]},
      { name: '電子琴', prompt: '電子琴',
        canned_bridge: 'electronic_keyboard',
        difficulty: 2, components: 4,
        challenges: [
          { tag: 'cable_routing', icon: '🔗', label: '按鍵矩陣',
            preview: '多個按鍵走線密集，需有序排列避免短路' },
          { tag: 'port_orient', icon: '🔊', label: '使用者介面',
            preview: '按鍵朝上、喇叭朝前，殼體需雙面開孔' },
        ]},
    ],
  },
  // 2026-05-08 移除 Wearables category（與 training/config.py SSOT 一致；
  // 計步器 / 發光領結 / 導盲手環 屬戶外/穿戴 → Layer 4 進階未來工作）
  Security: {
    label: '安全防護', icon: '🔒',
    templates: [
      { name: '防盜鈴', prompt: '防盜鈴',
        canned_bridge: 'burglar_alarm',
        difficulty: 1, components: 3,
        challenges: [
          { tag: 'port_orient', icon: '👁️', label: '偵測範圍',
            preview: 'PIR 感測器需朝外，偵測角度影響安裝位置' },
          { tag: 'low_power', icon: '🔋', label: '待機功耗',
            preview: '長時間待機 + 觸發瞬間大音量，電源設計關鍵' },
        ]},
      { name: '門禁系統', prompt: '門禁系統',
        canned_bridge: 'access_control',
        difficulty: 3, components: 5,
        challenges: [
          { tag: 'high_current', icon: '⚡', label: '電磁鎖驅動',
            preview: '電磁鎖 500mA，需繼電器 + 獨立電源' },
          { tag: 'i2c', icon: '🔌', label: '多裝置通訊',
            preview: 'RFID + OLED + 蜂鳴器，I/O 腳位分配緊湊' },
          { tag: 'structural', icon: '🔩', label: '門框安裝',
            preview: '殼體需配合門框固定，螺絲柱位置受限' },
        ]},
      { name: '警報器', prompt: '警報器',
        canned_bridge: 'alarm_siren',
        difficulty: 2, components: 4,
        challenges: [
          { tag: 'port_orient', icon: '🔊', label: '音訊方向',
            preview: '蜂鳴器 / 喇叭朝外，最大化警報音量' },
          { tag: 'thermal', icon: '🔥', label: '持續運作',
            preview: '警報模式持續驅動，需考慮長時間散熱' },
        ]},
    ],
  },
  Education: {
    label: '教育工具', icon: '📚',
    templates: [
      { name: '倒數計時器', prompt: '倒數計時器',
        canned_bridge: 'countdown_timer',
        difficulty: 1, components: 3,
        challenges: [
          { tag: 'port_orient', icon: '👁️', label: '顯示方向',
            preview: 'OLED/LCD 需面朝使用者，影響殼體正面開窗' },
          { tag: 'low_power', icon: '🔋', label: '電池供電',
            preview: '桌面使用可選 USB 或電池，需保留充電孔' },
        ]},
      { name: '語音導覽機', prompt: '語音導覽機',
        canned_bridge: 'voice_guide',
        difficulty: 2, components: 4,
        challenges: [
          { tag: 'port_orient', icon: '🔊', label: '音訊方向',
            preview: '喇叭需清楚傳達語音，開孔設計影響音質' },
          { tag: 'cable_routing', icon: '🔗', label: '按鍵布線',
            preview: '多個選擇按鍵 + 音訊模組，線路需整理' },
        ]},
    ],
  },
};

Object.assign(window, { ROLE_COLOR, CHALLENGE_CATALOG });
