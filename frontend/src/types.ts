export type Money = string;
export interface User {
  id: number;
  username: string;
  full_name: string;
  role: "admin" | "employee";
  is_active: boolean;
}
export interface Settings {
  store_name: string;
  currency: string;
  timezone: string;
}
export interface Me {
  user: User;
  settings: Settings;
  today: string;
}
export interface Totals {
  id: number;
  business_date: string;
  status: "open" | "closed";
  version: number;
  opening_cash: Money;
  total_sales: Money;
  pos_sales: Money;
  cash_sales: Money;
  new_credit_sales: Money;
  cash_collections: Money;
  card_collections: Money;
  bank_collections: Money;
  noncash_collections: Money;
  cash_purchases: Money;
  cash_expenses: Money;
  deposits: Money;
  withdrawals: Money;
  cash_refunds: Money;
  expected_cash: Money;
  actual_cash: Money | null;
  difference: Money | null;
  reconciliation_status: "pending" | "balanced" | "shortage" | "surplus";
  reconciliation_message: string;
  counted_at: string | null;
  count_stale: boolean;
}
export interface Customer {
  id: number;
  name: string;
  phone: string | null;
  notes: string;
  outstanding: Money;
  debt_count: number;
}
export interface Financial {
  id: number;
  amount: Money;
  created_by: number;
  created_at: string;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  session_id: number | null;
  notes?: string;
}
export interface Debt extends Financial {
  customer_id: number;
  customer_name?: string;
  debt_date: string;
  due_date: string | null;
  kind: "credit" | "opening";
  paid: Money;
  remaining: Money;
  debt_status: "unpaid" | "partial" | "paid" | "cancelled";
}
export interface Payment extends Financial {
  debt_id: number;
  payment_date: string;
  payment_method: string;
  customer_name?: string;
  recorded_by_name?: string;
}
export interface Purchase extends Financial {
  purchase_date: string;
  description: string;
  supplier: string | null;
  payment_method: string;
  from_drawer: boolean;
  invoice_number: string | null;
}
export interface Movement extends Financial {
  movement_date: string;
  kind: string;
  description: string;
  responsible_user_id: number;
  purchase_id: number | null;
  debt_payment_id: number | null;
}
export interface Snapshot {
  id: number;
  note: string;
  approved_by: number;
  approved_at: string;
  totals: Totals;
}
export interface DailySession {
  id: number;
  business_date: string;
  opening_cash: Money;
  total_sales: Money;
  pos_sales: Money;
  notes: string;
  version: number;
  status: "open" | "closed";
  responsible_name: string;
  closed_at: string | null;
  actual_cash: Money | null;
  totals: Totals;
  debts: Debt[];
  payments: Payment[];
  purchases: Purchase[];
  movements: Movement[];
  snapshots: Snapshot[];
}
export interface Current {
  session: DailySession | null;
  next_opening_cash: Money | null;
  last_business_date: string | null;
}
export interface Statement {
  customer: Customer;
  debts: Debt[];
  payments: Payment[];
  original: Money;
  paid: Money;
  outstanding: Money;
  entries: {
    id: number;
    date: string;
    kind: string;
    amount: Money;
    running_balance: Money;
    cancelled: boolean;
    payment_method?: string;
    debt_kind?: string;
  }[];
}
export interface Transaction extends Financial {
  category: string;
  description: string;
  date: string;
  kind?: string;
  payment_method?: string;
  from_drawer?: boolean;
  recorded_by_name: string;
}
export interface Report {
  start: string;
  end: string;
  totals: Omit<
    Totals,
    | "id"
    | "business_date"
    | "status"
    | "version"
    | "opening_cash"
    | "expected_cash"
    | "actual_cash"
    | "difference"
    | "counted_at"
    | "count_stale"
    | "reconciliation_status"
    | "reconciliation_message"
  > & { total_shortages: Money; total_surpluses: Money; net_difference: Money };
  daily: Totals[];
  session_count: number;
  closed_count: number;
  balance_at_end: {
    business_date: string;
    opening_cash: Money;
    expected_cash: Money;
    status: string;
    difference: Money | null;
    reconciliation_message: string;
  } | null;
  last_count: {
    business_date: string;
    amount: Money;
    counted_at: string;
    stale: boolean;
    session_id: number;
  } | null;
  outstanding_debts_now: Money;
  outstanding_as_of: string;
  recent_transactions: Transaction[];
  currency: string;
  timezone: string;
}
export interface Audit {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  user_name: string;
  reason: string;
  created_at: string;
  before_json: string | null;
  after_json: string | null;
}
export type Page =
  | "dashboard"
  | "daily"
  | "history"
  | "customers"
  | "movements"
  | "reports"
  | "settings";
