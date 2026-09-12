type JapaneseTeam = {
  aliases: readonly string[]
  players: readonly string[]
}

// 2026-27 season. Keep this list small and explicit so transfer updates are easy to review.
const JAPANESE_TEAMS: readonly JapaneseTeam[] = [
  { aliases: ['Aston Villa'], players: ['鈴木彩艶'] },
  {
    aliases: ['Brighton & Hove Albion', 'Brighton and Hove Albion', 'Brighton Hove Albion', 'Brighton'],
    players: ['三笘薫'],
  },
  { aliases: ['Coventry City', 'Coventry'], players: ['坂元達裕'] },
  { aliases: ['Crystal Palace'], players: ['鎌田大地', '冨安健洋'] },
  { aliases: ['Hull City', 'Hull'], players: ['守田英正'] },
  { aliases: ['Ipswich Town', 'Ipswich'], players: ['前田大然'] },
  { aliases: ['Leeds United', 'Leeds'], players: ['田中碧'] },
  { aliases: ['Liverpool'], players: ['遠藤航'] },
  { aliases: ['Real Sociedad', 'Real Sociedad de Fútbol', 'Real Sociedad de Futbol'], players: ['久保建英'] },
  { aliases: ['Valencia', 'Valencia CF', 'Valencia Club de Fútbol', 'Valencia Club de Futbol'], players: ['佐藤龍之介'] },
  { aliases: ['Bayern München', 'Bayern Munich', 'FC Bayern München'], players: ['伊藤洋輝'] },
  { aliases: ['Eintracht Frankfurt'], players: ['堂安律', '小杉啓太', '神代慶人'] },
  {
    aliases: ['Borussia Mönchengladbach', 'Borussia Monchengladbach'],
    players: ['板倉滉', '町野修斗', '橋岡大樹', '宇野禅斗'],
  },
  { aliases: ['FSV Mainz 05', '1. FSV Mainz 05', 'Mainz 05'], players: ['佐野海舟', '川﨑颯太'] },
  { aliases: ['SC Freiburg', 'Sport-Club Freiburg'], players: ['鈴木唯人', '山本理仁', '後藤啓介'] },
  { aliases: ['1899 Hoffenheim', 'TSG Hoffenheim'], players: ['町田浩樹'] },
  { aliases: ['FC Schalke 04', 'Schalke 04'], players: ['田中聡'] },
  { aliases: ['AS Monaco', 'AS Monaco FC', 'Monaco'], players: ['南野拓実'] },
  {
    aliases: ['LE Havre', 'Le Havre', 'Le Havre AC', 'Havre AC'],
    players: ['瀬古歩夢', '中村草太', '水多海斗'],
  },
  { aliases: ['Lille', 'Lille OSC', 'LOSC', 'LOSC Lille'], players: ['上田綺世'] },
  { aliases: ['Lyon', 'Olympique Lyonnais', 'Olympique Lyon'], players: ['中村敬斗'] },
]

const normalizeTeamName = (name: string) =>
  name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()

const playersByTeamName = new Map<string, readonly string[]>(
  JAPANESE_TEAMS.flatMap((team) =>
    team.aliases.map((alias) => [normalizeTeamName(alias), team.players] as const),
  ),
)

export const japanesePlayersForTeam = (teamName: string): readonly string[] =>
  playersByTeamName.get(normalizeTeamName(teamName)) ?? []
