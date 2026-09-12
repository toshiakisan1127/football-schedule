const J1_TEAM_NAMES_BY_ID: Readonly<Record<string, string>> = {
  '281': '柏レイソル',
  '282': 'サンフレッチェ広島',
  '283': '清水エスパルス',
  '285': 'V・ファーレン長崎',
  '287': '浦和レッズ',
  '288': '名古屋グランパス',
  '289': 'ヴィッセル神戸',
  '290': '鹿島アントラーズ',
  '291': 'セレッソ大阪',
  '292': 'FC東京',
  '293': 'ガンバ大阪',
  '294': '川崎フロンターレ',
  '296': '横浜F・マリノス',
  '301': 'ジェフユナイテッド千葉',
  '302': '京都サンガF.C.',
  '303': 'FC町田ゼルビア',
  '305': '水戸ホーリーホック',
  '306': '東京ヴェルディ',
  '310': 'ファジアーノ岡山',
  '316': 'アビスパ福岡',
}

export const j1TeamName = (teamId: string, fallbackName: string) =>
  J1_TEAM_NAMES_BY_ID[teamId] ?? fallbackName

export const j1LiveEventTeamName = (teamId: string | null, fallbackName: string | null) =>
  teamId ? J1_TEAM_NAMES_BY_ID[teamId] ?? fallbackName : fallbackName
