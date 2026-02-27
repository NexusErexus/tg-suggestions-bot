import logging
import psycopg2.extras

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import *

# Creating bot and dispatcher
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db_user = USERNAME

# Creating and accessing database
base = psycopg2.connect(host=HOSTNAME, dbname=DATABASE, user=USERNAME, password=DB_PASS, port=PORT_ID)
cursor = base.cursor(cursor_factory=psycopg2.extras.DictCursor)
try:
    cursor.execute('CREATE TABLE IF NOT EXISTS ban_id (user_id bigint PRIMARY KEY, ban_reason text)')
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS message_id (
        user_message_id INT,
        bot_message_id INT,
        datatime TIMESTAMP,
        tg_user_id BIGINT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_message (
        id SERIAL PRIMARY KEY,
        message_id BIGINT UNIQUE NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media_group_messages (
        keyboard_message_id BIGINT NOT NULL,
        album_message_id BIGINT NOT NULL,
        file_id TEXT,
        media_type TEXT,
        caption TEXT
    )
    """)

    # Migration: добавляем поля если их нет
    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'media_group_messages' AND column_name = 'file_id') THEN
                ALTER TABLE media_group_messages ADD COLUMN file_id TEXT;
                ALTER TABLE media_group_messages ADD COLUMN media_type TEXT;
                ALTER TABLE media_group_messages ADD COLUMN caption TEXT;
            END IF;
        END $$;
    """)

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
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'message_id' AND column_name = 'username') THEN
                ALTER TABLE message_id ADD COLUMN username text;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'message_id' AND column_name = 'source') THEN
                ALTER TABLE message_id ADD COLUMN source text;
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