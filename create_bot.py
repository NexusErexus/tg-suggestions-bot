import logging
import psycopg2.extras

from aiogram import Bot, Dispatcher

from config import *

# Creating bot and dispatcher with built-in functions
bot = Bot(TOKEN)
dp = Dispatcher(bot)
db_user = USERNAME

# Creating and accessing database for banning/unbanning users and editing messages, creating routine cleaner function
base = psycopg2.connect(host=HOSTNAME, dbname=DATABASE, user=USERNAME, password=DB_PASS, port=PORT_ID)
cursor = base.cursor(cursor_factory=psycopg2.extras.DictCursor)
try:
    cursor.execute(f'CREATE TABLE IF NOT EXISTS ban_id (user_id bigint PRIMARY KEY, ban_reason text)')
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS message_id (
        user_message_id INT,
        bot_message_id INT,
        datatime TIMESTAMP,
        tg_user_id BIGINT
    )
    """)

    # Migration: добавляем full_name если его ещё нет
    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'ban_id' AND column_name = 'full_name') THEN
                ALTER TABLE ban_id ADD COLUMN full_name text;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'message_id' AND column_name = 'full_name') THEN
                ALTER TABLE message_id ADD COLUMN full_name text;
            END IF;
        END $$;
    """)

    cursor.execute(f"""
    create or replace function expire_table_delete_old_rows() returns trigger
        language plpgsql
    as
    $$
    DECLARE
      row_count int;

    BEGIN
      DELETE FROM message_id WHERE datatime < NOW() - INTERVAL '{REMOVAL_INTERVAL}';
      IF found THEN
        GET DIAGNOSTICS row_count = ROW_COUNT;
        RAISE NOTICE 'DELETEd % row(s) FROM message_id', row_count;
      END IF;
      RETURN NEW;
    END;
    $$;

    alter function expire_table_delete_old_rows() owner to {db_user};
    """)
    base.commit()
    logging.info("Tables were successfully created, routine function was set!")
except Exception as e:
    logging.error(e)