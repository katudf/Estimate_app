# setup_database.py (または同等のデータベース初期化ファイル)

import sqlite3
from constants import DATABASE_FILE_NAME # constants.py からインポート

def create_connection(db_file):
    """ データベースファイルへの接続を作成する """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # print(f"SQLite DB バージョン: {sqlite3.sqlite_version}") # 開発時のみ
        return conn
    except sqlite3.Error as e:
        print(f"データベース接続エラー: {e}")
    return conn

def create_table(conn, create_table_sql):
    """ テーブルを作成する """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except sqlite3.Error as e:
        print(f"テーブル作成エラー: {e}")

def setup_database():
    """ データベースとテーブルをセットアップする """
    conn = create_connection(DATABASE_FILE_NAME)

    if conn is not None:
        # estimates テーブル作成 SQL (金額カラムの型を REAL に変更)
        sql_create_estimates_table = """ CREATE TABLE IF NOT EXISTS estimates (
                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            base_estimate_id INTEGER,
                                            revision_number INTEGER NOT NULL DEFAULT 0,
                                            project_name TEXT,
                                            client_name TEXT,
                                            period_text TEXT,
                                            subtotal_amount REAL,
                                            tax_amount REAL,
                                            total_amount REAL,
                                            created_at TEXT,
                                            updated_at TEXT,
                                            FOREIGN KEY (base_estimate_id) REFERENCES estimates (id)
                                        ); """

        # details テーブル作成 SQL (項目変更と型変更)
        sql_create_details_table = """CREATE TABLE IF NOT EXISTS details (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        estimate_id INTEGER NOT NULL,
                                        row_order INTEGER NOT NULL,
                                        name_text TEXT,          /* 「名称」 */
                                        specification_text TEXT, /* 「仕様」 - 新規追加 */
                                        quantity REAL,
                                        unit_text TEXT,
                                        unit_price REAL,
                                        amount REAL,
                                        summary_text TEXT,       /* 「摘要」 - remarks_text から変更 */
                                        FOREIGN KEY (estimate_id) REFERENCES estimates (id)
                                    );"""

        create_table(conn, sql_create_estimates_table)
        create_table(conn, sql_create_details_table)
        print(f"データベース '{DATABASE_FILE_NAME}' とテーブルが正常にセットアップされました。")
        conn.close()
    else:
        print("エラー！データベース接続を作成できませんでした。")

if __name__ == '__main__':
    # 既存の estimates.db があれば、手動で削除してから実行してください。
    # import os
    # if os.path.exists(DATABASE_FILE_NAME):
    # os.remove(DATABASE_FILE_NAME)
    # print(f"既存のデータベース '{DATABASE_FILE_NAME}' を削除しました。")
    setup_database()