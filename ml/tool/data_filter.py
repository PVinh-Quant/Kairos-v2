import os
import polars as pl

INPUT_FILE = r"d:\The V\KAIROS QUANT SYSTEM v2.0\ml\trang_thai_thi_truong_ml\du_lieu_ml\trading_memory.csv"
OUTPUT_FILE = r"d:\The V\KAIROS QUANT SYSTEM v2.0\ml\trang_thai_thi_truong_ml\du_lieu_ml\trading_memory_balanced.csv"


def tao_log_can_bang():
    """Đọc trading_memory.csv, cân bằng nhãn theo lớp thiểu số và xuất file mới."""
    print(f"📂 Đang đọc dữ liệu từ: {INPUT_FILE}...")

    if not os.path.exists(INPUT_FILE):
        print("❌ Không tìm thấy file log gốc.")
        return

    try:

        df = pl.read_csv(INPUT_FILE)


        df_clean = df.with_columns(
            pl.col("correct").cast(pl.Int64, strict=False)
        ).drop_nulls(subset=["correct"])

        if df_clean.is_empty():
            print("⚠️ File log không có dữ liệu 'correct' hợp lệ nào.")
            return


        count_df = df_clean.group_by("correct").count().sort("correct")
        print("\n📊 Phân bố dữ liệu GỐC:")
        print(count_df)

        if count_df.height < 2:
            print("⚠️ Chỉ có 1 loại nhãn duy nhất. Không cần cân bằng.")
            df_clean.write_csv(OUTPUT_FILE)
            return


        min_samples = count_df["count"].min()
        print(f"\n✂️ Sẽ cắt gọt dữ liệu về mức thấp nhất: {min_samples} dòng/loại")



        labels = count_df["correct"].to_list()
        balanced_dfs = [
            df_clean.filter(pl.col("correct") == label).sample(n=min_samples, seed=42)
            for label in labels
        ]


        df_final = pl.concat(balanced_dfs).sample(fraction=1.0, shuffle=True, seed=42)


        df_final.write_csv(OUTPUT_FILE)

        print("-" * 50)
        print(f"✅ ĐÃ TẠO FILE LOG CÂN BẰNG: {OUTPUT_FILE}")
        print(f"📊 Tổng số dòng: {len(df_final)}")
        print(f"🔍 Phân bố MỚI (Đều tăm tắp):")
        print(df_final.group_by("correct").count().sort("correct"))
        print("-" * 50)

        print(
            "💡 Gợi ý: Hãy đổi tên file này thành 'trading_memory.csv' nếu muốn AI học ngay lập tức."
        )

    except Exception as e:
        print(f"❌ Lỗi xử lý: {e}")


if __name__ == "__main__":
    tao_log_can_bang()
