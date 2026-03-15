export interface DateRecord {
  date: string
  holdings: Array<{
    code: string
    name: string
    weight: number
  }>
  cash_pct: number
  n_stocks: number
  stock_weight: number
  taiex: number
}

export interface EtfPageData {
  dates: string[]
  n_dates: number
  date_records: DateRecord[]
  cash_series: Array<{ date: string; cash_pct: number; n_holdings?: number; n_stocks?: number }>
}

export type EtfPagesData = Record<string, EtfPageData>
