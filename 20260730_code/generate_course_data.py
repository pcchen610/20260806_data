"""Generate a reproducible e-commerce dataset for the 16-lesson course.

這支程式用來產生商業分析課程會用到的模擬電商資料。
資料包含顧客、商品、訂單、訂單明細、網站瀏覽 session、事件紀錄、A/B 測試分組，
並同時輸出成 CSV 檔與 SQLite 資料庫，方便後續課程用 pandas 或 SQL 分析。
"""

from __future__ import annotations

import csv
import math
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


SEED = 20260217
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)


def random_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """在指定日期區間內隨機抽出一天。"""
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, delta_days))


def write_csv(path: Path, rows: list[dict], headers: list[str]) -> None:
    """將 list[dict] 資料寫成 CSV 檔。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def generate_customers(rng: random.Random, n: int = 2500) -> list[dict]:
    """產生顧客主檔資料。"""
    channels = ["organic", "ads", "referral", "partner", "social"]
    cities = ["Taipei", "Taichung", "Kaohsiung", "Tainan", "Hsinchu", "Taoyuan"]
    segments = ["new", "growth", "vip"]
    rows = []
    for cid in range(1, n + 1):
        # 註冊日可能早於正式觀測期間，這樣資料中會同時有新客與既有顧客。
        signup = random_date(rng, START_DATE - timedelta(days=400), END_DATE - timedelta(days=30))

        # 用權重控制顧客組成：一般新客最多，VIP 最少，較接近真實商業情境。
        segment = rng.choices(segments, weights=[0.6, 0.3, 0.1])[0]
        rows.append(
            {
                "customer_id": cid,
                "signup_date": signup.date().isoformat(),
                "acquisition_channel": rng.choice(channels),
                "city": rng.choice(cities),
                "segment": segment,
            }
        )
    return rows


def generate_products(rng: random.Random) -> list[dict]:
    """產生商品主檔資料，每個品類各 10 個商品。"""
    categories = ["electronics", "home", "beauty", "grocery", "sports", "fashion"]
    rows = []
    pid = 1
    for category in categories:
        for _ in range(10):
            # TWD is represented as integer dollars for this course dataset.
            price = rng.randint(100, 5000)
            rows.append(
                {
                    "product_id": pid,
                    "category": category,
                    "unit_price": price,
                }
            )
            pid += 1
    return rows


def generate_orders_and_items(
    rng: random.Random, customers: list[dict], products: list[dict], n_orders: int = 22000
) -> tuple[list[dict], list[dict]]:
    """產生訂單表與訂單明細表。"""
    payment_types = ["card", "atm", "cod", "wallet"]
    statuses = ["completed", "cancelled", "refunded"]

    # 先建立查表用的 dict/list，讓後面可以快速依商品 ID 找價格、依顧客清單抽樣。
    product_prices = {int(p["product_id"]): int(p["unit_price"]) for p in products}
    customer_ids = [int(c["customer_id"]) for c in customers]

    orders: list[dict] = []
    items: list[dict] = []
    for oid in range(1, n_orders + 1):
        order_dt = random_date(rng, START_DATE, END_DATE)

        # 大多數訂單為完成狀態，少數取消或退款。
        status = rng.choices(statuses, weights=[0.93, 0.04, 0.03])[0]
        customer_id = rng.choice(customer_ids)

        # 不同付款方式也用權重模擬實務上的使用比例。
        payment_type = rng.choices(payment_types, weights=[0.5, 0.25, 0.1, 0.15])[0]

        orders.append(
            {
                "order_id": oid,
                "customer_id": customer_id,
                "order_date": order_dt.date().isoformat(),
                "status": status,
                "payment_type": payment_type,
            }
        )

        # 一張訂單可包含多個商品，且通常 1 到 2 個品項最多。
        n_items = rng.choices([1, 2, 3, 4], weights=[0.45, 0.35, 0.15, 0.05])[0]
        for _ in range(n_items):
            product_id = rng.randint(1, len(products))
            qty = rng.choices([1, 2, 3], weights=[0.8, 0.17, 0.03])[0]
            list_price = product_prices[product_id]

            # 折扣率保留在明細層，後續可練習計算營收、折扣影響與毛額。
            discount_rate = rng.choices([0, 0.05, 0.1, 0.15, 0.2], weights=[0.4, 0.25, 0.2, 0.1, 0.05])[0]
            items.append(
                {
                    "order_id": oid,
                    "product_id": product_id,
                    "quantity": qty,
                    "unit_price": int(list_price),
                    "discount_rate": discount_rate,
                }
            )
    return orders, items


def generate_sessions_and_events(
    rng: random.Random, customers: list[dict], orders: list[dict], items: list[dict], n_sessions: int = 70000
) -> tuple[list[dict], list[dict], list[dict]]:
    """產生網站 session、事件紀錄，以及 A/B 測試分組資料。"""
    devices = ["mobile", "desktop", "tablet"]
    traffic = ["seo", "sem", "direct", "social", "email"]
    campaigns = ["none", "spring_sale", "double11", "new_user", "retarget"]

    customer_ids = [int(c["customer_id"]) for c in customers]
    customer_map = {int(c["customer_id"]): c for c in customers}

    # 事件中的 purchase 只應連到已完成訂單，因此先篩掉取消與退款的訂單。
    order_map = {int(o["order_id"]): o for o in orders if o["status"] == "completed"}

    # 彙總每張訂單的實際營收：數量 * 單價 * (1 - 折扣率)。
    item_rev: dict[int, float] = defaultdict(float)
    for row in items:
        oid = int(row["order_id"])
        amount = int(row["quantity"]) * float(row["unit_price"]) * (1 - float(row["discount_rate"]))
        item_rev[oid] += amount

    assignments = []
    assign_map = {}
    for cid in customer_ids:
        # 每位顧客隨機分配到 A/B 其中一組，用來模擬實驗資料。
        group = rng.choices(["A", "B"], weights=[0.5, 0.5])[0]
        assign_date = random_date(rng, START_DATE, START_DATE + timedelta(days=15))
        assignments.append(
            {
                "customer_id": cid,
                "experiment_group": group,
                "assign_date": assign_date.date().isoformat(),
            }
        )
        assign_map[cid] = group

    sessions = []
    events = []
    order_ids = list(order_map.keys())
    orders_by_customer: dict[int, list[int]] = defaultdict(list)
    for oid, o in order_map.items():
        # 建立「顧客 -> 已完成訂單」的對應，讓購買事件盡量連回同一顧客的訂單。
        orders_by_customer[int(o["customer_id"])].append(oid)

    def sigmoid(x: float) -> float:
        """把任意分數轉成 0 到 1 之間的機率。"""
        return 1.0 / (1.0 + math.exp(-x))

    # 以下權重用來模擬不同因素對轉換率的影響。
    # 正值表示較容易購買，負值表示較不容易購買。
    device_w = {"mobile": -0.25, "desktop": 0.2, "tablet": -0.6}
    traffic_w = {"seo": 0.15, "sem": -0.05, "direct": 0.0, "social": -0.1, "email": 0.35}
    campaign_w = {"none": -0.15, "spring_sale": 0.12, "double11": 0.24, "new_user": 0.08, "retarget": 0.5}
    segment_w = {"new": -0.3, "growth": 0.08, "vip": 0.45}
    hour_w = [(-0.2 if h <= 6 else 0.12 if 19 <= h <= 23 else 0.0) for h in range(24)]

    for sid in range(1, n_sessions + 1):
        cid = rng.choice(customer_ids)
        start = random_date(rng, START_DATE, END_DATE) + timedelta(hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        device = rng.choices(devices, weights=[0.62, 0.33, 0.05])[0]
        source = rng.choice(traffic)
        campaign = rng.choices(campaigns, weights=[0.55, 0.12, 0.08, 0.15, 0.1])[0]
        group = assign_map[cid]

        # session 是一次網站造訪，紀錄顧客、時間、裝置、流量來源與活動資訊。
        sessions.append(
            {
                "session_id": sid,
                "customer_id": cid,
                "session_start": start.isoformat(timespec="minutes"),
                "device": device,
                "traffic_source": source,
                "campaign": campaign,
                "experiment_group": group,
            }
        )

        n_views = rng.randint(1, 5)
        for i in range(n_views):
            # 每個 session 至少有 page_view 事件，代表瀏覽頁面。
            t = start + timedelta(minutes=i * rng.randint(1, 5))
            events.append(
                {
                    "event_id": len(events) + 1,
                    "session_id": sid,
                    "event_type": "page_view",
                    "event_time": t.isoformat(timespec="minutes"),
                    "order_id": "",
                    "revenue": 0.0,
                }
            )

        # 加入購物車的機率會受到活動與裝置影響，模擬行銷活動對漏斗前段的提升。
        add_to_cart_prob = 0.16
        add_to_cart_prob += 0.1 if campaign in {"retarget", "double11"} else 0.0
        add_to_cart_prob += 0.06 if device == "desktop" else 0.0
        add_to_cart_prob -= 0.04 if source == "social" else 0.0

        # 避免機率過低或過高，讓資料仍保持合理範圍。
        add_to_cart_prob = min(max(add_to_cart_prob, 0.05), 0.65)
        has_cart = rng.random() < add_to_cart_prob
        if has_cart:
            t = start + timedelta(minutes=rng.randint(1, 15))
            events.append(
                {
                    "event_id": len(events) + 1,
                    "session_id": sid,
                    "event_type": "add_to_cart",
                    "event_time": t.isoformat(timespec="minutes"),
                    "order_id": "",
                    "revenue": 0.0,
                }
            )

        segment = customer_map[cid]["segment"]

        # purchase_logit 是購買傾向分數，將多個因素加總後再用 sigmoid 轉成購買機率。
        purchase_logit = -2.2
        purchase_logit += device_w[device]
        purchase_logit += traffic_w[source]
        purchase_logit += campaign_w[campaign]
        purchase_logit += segment_w[segment]
        purchase_logit += hour_w[start.hour]
        purchase_logit += 1.15 if has_cart else 0.0
        purchase_logit += 0.08 if group == "B" else 0.0

        # B 組多加 0.08，代表實驗組有一點點轉換率提升，可用來練習 A/B test 分析。
        purchase_prob = min(max(sigmoid(purchase_logit), 0.01), 0.9)
        if rng.random() < purchase_prob:
            customer_orders = orders_by_customer.get(cid)

            # 優先挑同一顧客的訂單；若沒有已完成訂單，才從所有完成訂單中抽一張。
            oid = rng.choice(customer_orders) if customer_orders else rng.choice(order_ids)
            t = start + timedelta(minutes=rng.randint(3, 25))
            events.append(
                {
                    "event_id": len(events) + 1,
                    "session_id": sid,
                    "event_type": "purchase",
                    "event_time": t.isoformat(timespec="minutes"),
                    "order_id": oid,
                    "revenue": round(item_rev.get(oid, 0.0), 2),
                }
            )

    return sessions, events, assignments


def write_sqlite(db_path: Path, tables: dict[str, list[dict]]) -> None:
    """將多個 list[dict] 資料表寫入 SQLite 資料庫。"""
    def infer_sqlite_type(rows: list[dict], col: str) -> str:
        """依欄位的第一個非空值推估 SQLite 欄位型別。"""
        for row in rows:
            value = row.get(col)
            if value is None or value == "":
                continue
            if isinstance(value, bool):
                return "INTEGER"
            if isinstance(value, int):
                return "INTEGER"
            if isinstance(value, float):
                return "REAL"
            return "TEXT"
        return "TEXT"

    if db_path.exists():
        # 重新產生資料庫時先刪除舊檔，避免保留過期資料表。
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        for name, rows in tables.items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            col_defs = ", ".join(f"{c} {infer_sqlite_type(rows, c)}" for c in cols)
            conn.execute(f"CREATE TABLE {name} ({col_defs});")
            placeholders = ", ".join("?" for _ in cols)

            # executemany 一次寫入多筆資料，比逐筆 execute 更適合大量資料。
            conn.executemany(
                f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({placeholders});",
                [[r[c] for c in cols] for r in rows],
            )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    """主流程：產生所有資料表，輸出 CSV，並建立 SQLite 資料庫。"""
    # 固定亂數種子，確保每次執行都產生相同資料，方便教學與作業對答案。
    rng = random.Random(SEED)

    # __file__ 是目前腳本位置；parent 代表腳本所在資料夾。
    # 因此 data/raw 會產生在 generate_course_data.py 的同一層。
    root = Path(__file__).resolve().parent
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 依照資料表之間的依賴順序產生資料。
    # 例如訂單需要先有顧客與商品，事件中的購買也需要引用訂單。
    customers = generate_customers(rng)
    products = generate_products(rng)
    orders, order_items = generate_orders_and_items(rng, customers, products)
    sessions, events, assignments = generate_sessions_and_events(rng, customers, orders, order_items)

    # 分別輸出 CSV，方便 pandas、Excel 或 BI 工具讀取。
    write_csv(raw_dir / "customers.csv", customers, list(customers[0].keys()))
    write_csv(raw_dir / "products.csv", products, list(products[0].keys()))
    write_csv(raw_dir / "orders.csv", orders, list(orders[0].keys()))
    write_csv(raw_dir / "order_items.csv", order_items, list(order_items[0].keys()))
    write_csv(raw_dir / "sessions.csv", sessions, list(sessions[0].keys()))
    write_csv(raw_dir / "events.csv", events, list(events[0].keys()))
    write_csv(raw_dir / "ab_assignments.csv", assignments, list(assignments[0].keys()))

    # 同一批資料也寫成 SQLite，方便課程練習 SQL 查詢與資料庫分析。
    write_sqlite(
        raw_dir / "course.db",
        {
            "customers": customers,
            "products": products,
            "orders": orders,
            "order_items": order_items,
            "sessions": sessions,
            "events": events,
            "ab_assignments": assignments,
        },
    )
    print("Generated dataset at data/raw/ with CSV files and course.db")

if __name__ == "__main__":
    main()
