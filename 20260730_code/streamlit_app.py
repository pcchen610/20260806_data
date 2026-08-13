import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


#設定網頁標題
st.title("資料視覺圖表")


#讀取資料
orders = pd.read_csv('data/raw/orders.csv')
items = pd.read_csv('data/raw/order_items.csv')
#合併資料
df = orders.merge(items, on='order_id')
st.write("### 合併後的資料表")
st.write(df.head())
#計算每筆商品的營收金額
df['amount']=(
    df['quantity'] * df['unit_price'] * (1-df['discount_rate'])
)
#轉換日期
df['order_date']=pd.to_datetime(df['order_date'])
#選擇訂單狀態
status_list = df['status'].unique()
status = st.selectbox("選擇訂單狀態", status_list)
data = df[ df['status']== status ]
#st.write(data.head())
#選擇圖表類型
chart_type = st.selectbox(
    "選擇圖表類型",
    [
        '每月銷售金額',
        '付款方式訂單數',
        '訂單金額',
        '各付款方式金額',
        '商品單價與購買數量'
    ]
)
#顯示圖表
if st.button("顯示圖表"):

    #線條圖1
    if chart_type == '每月銷售金額':
        data = data.copy()
        data['month']=data['order_date'].dt.to_period('M')
        m_sales = (
            data.groupby('month')['amount'].sum()
        )
        m_sales.index = m_sales.index.astype(str)
        fig,ax = plt.subplots()
        ax.plot(
            m_sales.index,
            m_sales.values,
            marker='o'
        )
        ax.set_title("M-sales")
        ax.set_xlabel("M")
        ax.set_ylabel("$")
        plt.xticks(rotation=45)
        st.pyplot(fig)

    #長條圖2
    elif chart_type == '付款方式訂單數':
        pay_count = data.groupby('payment_type')['order_id'].nunique()
        fig,ax = plt.subplots()
        ax.bar(
            pay_count.index,
            pay_count.values
        )
        ax.set_title("payment_type+Orders")
        ax.set_xlabel("payment_type")
        ax.set_ylabel("Orders")
        st.pyplot(fig)

    #直方圖3
    elif chart_type == '訂單金額':
        order_amount = data.groupby('order_id')['amount'].sum()
        fig,ax = plt.subplots()
        ax.hist(
            order_amount,
            bins=30
        )
        ax.set_title("order_amount")
        ax.set_xlabel("order_amount")
        ax.set_ylabel("Q")
        st.pyplot(fig)


    #箱形圖4:'各付款方式金額'
    elif chart_type == '各付款方式金額':  
        order_amount = (
            data.groupby(['order_id', 'payment_type'])['amount']
            .sum()
            .reset_index()
        )
        pays = order_amount['payment_type'].unique()
        boxData = []
        for i in pays:
            values = order_amount[ order_amount['payment_type']==i ]['amount']
            boxData.append(values)
        fig,ax = plt.subplots()
        ax.boxplot(
            boxData
        )
        ax.set_title("XXX")
        ax.set_xlabel("11")
        ax.set_ylabel("22")
        st.pyplot(fig)

    #散佈圖5
    elif chart_type == '商品單價與購買數量':        
        fig,ax = plt.subplots()
        ax.scatter(
            data['unit_price'],
            data['quantity']
        )
        ax.set_title("unit_price+quantity")
        ax.set_xlabel("unit_price")
        ax.set_ylabel("quantity")
        st.pyplot(fig)
   
else:
    st.info('尚未選擇')


