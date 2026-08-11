"""初學者練習：用四張 CSV 建立 Streamlit 商業指標儀表板。"""

from pathlib import Path

import pandas as pd
import streamlit as st


DATA_DIR = Path(__file__).parent / "data" / "raw"


@st.cache_data
def load_data() -> pd.DataFrame:
    """讀取並合併訂單、明細、顧客與商品資料。"""
    orders = pd.read_csv(DATA_DIR / "orders.csv", parse_dates=["order_date"])
    order_items = pd.read_csv(DATA_DIR / "order_items.csv")
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")

    # 先把訂單明細接上商品，再接訂單與顧客資料。
    sales = (
        order_items.merge(
            products[["product_id", "category"]],
            on="product_id",
            how="left",
            validate="many_to_one",
        )
        .merge(orders, on="order_id", how="left", validate="many_to_one")
        .merge(customers, on="customer_id", how="left", validate="many_to_one")
    )

    # 實際營收 = 數量 × 售價 ×（1 - 折扣率）。
    sales["revenue"] = (
        sales["quantity"] * sales["unit_price"] * (1 - sales["discount_rate"])
    )
    return sales


def format_money(value: float) -> str:
    return f"NT$ {value:,.0f}"


def main() -> None:
    st.set_page_config(page_title="銷售儀表板", page_icon="📊", layout="wide")
    st.title("📊 銷售商業指標儀表板")
    st.caption("資料來源：orders、order_items、customers、products｜僅計算已完成訂單")

    sales = load_data()
    completed = sales.loc[sales["status"].eq("completed")].copy()

    st.sidebar.header("篩選條件")
    min_date = completed["order_date"].min().date()
    max_date = completed["order_date"].max().date()
    date_range = st.sidebar.date_input(
        "訂單日期",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    segments = sorted(completed["segment"].dropna().unique())
    categories = sorted(completed["category"].dropna().unique())
    selected_segments = st.sidebar.multiselect("顧客分群", segments, default=segments)
    selected_categories = st.sidebar.multiselect("商品品類", categories, default=categories)

    filtered = completed[
        completed["segment"].isin(selected_segments)
        & completed["category"].isin(selected_categories)
    ]
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            filtered["order_date"].dt.date.between(start_date, end_date)
        ]

    if filtered.empty:
        st.warning("目前篩選條件沒有資料，請調整日期、顧客分群或商品品類。")
        st.stop()

    total_revenue = filtered["revenue"].sum()
    order_count = filtered["order_id"].nunique()
    customer_count = filtered["customer_id"].nunique()
    average_order_value = total_revenue / order_count

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("總營收", format_money(total_revenue))
    col2.metric("完成訂單數", f"{order_count:,}")
    col3.metric("平均訂單金額", format_money(average_order_value))
    col4.metric("購買顧客數", f"{customer_count:,}")

    left, right = st.columns(2)
    with left:
        st.subheader("每日營收趨勢")
        daily_revenue = (
            filtered.groupby("order_date", as_index=False)["revenue"].sum()
            .set_index("order_date")
        )
        st.line_chart(daily_revenue, y="revenue", y_label="營收")

    with right:
        st.subheader("各商品品類營收")
        category_revenue = (
            filtered.groupby("category", as_index=False)["revenue"]
            .sum()
            .sort_values("revenue", ascending=False)
            .set_index("category")
        )
        st.bar_chart(category_revenue, y="revenue", y_label="營收")

    st.subheader("顧客分群摘要")
    segment_summary = (
        filtered.groupby("segment", as_index=False)
        .agg(
            訂單數=("order_id", "nunique"),
            顧客數=("customer_id", "nunique"),
            營收=("revenue", "sum"),
        )
        .sort_values("營收", ascending=False)
    )
    segment_summary["平均訂單金額"] = segment_summary["營收"] / segment_summary["訂單數"]
    st.dataframe(
        segment_summary.style.format(
            {"訂單數": "{:,}", "顧客數": "{:,}", "營收": "{:,.0f}", "平均訂單金額": "{:,.0f}"}
        ),
        hide_index=True,
        use_container_width=True,
    )

    with st.expander("查看合併後資料（前 100 筆）"):
        display_columns = [
            "order_id",
            "order_date",
            "customer_id",
            "segment",
            "category",
            "quantity",
            "discount_rate",
            "revenue",
        ]
        st.dataframe(filtered[display_columns].head(100), hide_index=True)


if __name__ == "__main__":
    main()
