import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackContext, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Подключение к Google Sheets
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('studcomsummerbot-8c8b791264c5.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("StudcomSummer").worksheet("base")
    users = client.open("StudcomSummer").worksheet("users")
    comment = client.open("StudcomSummer").worksheet("comment")
except FileNotFoundError:
    logger.critical("ОШИБКА: Файл ключа 'studcomsummerbot-8c8b791264c5.json' не найден.")
    exit()
except Exception as e:
    logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к Google Sheets. {e}")
    exit()

# Этапы диалога
START, LAST_NAME, FIRST_NAME, SECOND_NAME, BIRTH_DATE, RULES = range(6)

async def find_info(update: Update, context: CallbackContext, last: str, first: str, second: str, bd: str,
                    is_new_user: bool = False):
    global_comment = comment.cell(1, 1).value
    if global_comment == 'None':
        global_comment = ''
    else:
        global_comment = '\n\n' + global_comment.replace('<br>', '\n')
    records = sheet.get_all_records()

    room = None
    lvl = None

    for rec in records:
        if rec['Фамилия'] == last and rec['Имя'] == first and rec['Дата рождения'] == bd and rec.get(
                'Отчество') == second:
            room, lvl = rec['Комната'], rec['Курс'];
            break

    if second == '':
        mini_space = ''
    else:
        mini_space = ' '

    if room and lvl == 1:
        neighbors = [f"{r['Фамилия']} {r['Имя']}{mini_space}{r['Отчество'].strip()}, {r['Курс']} курс" for r in records if
                     r['Комната'] == room]
        msg = f"В вашей комнате проживают:\n" + "\n".join(neighbors)
    elif room and room[-1] not in ['л', 'п']:
        neighbors = [f"{r['Фамилия']} {r['Имя']}{mini_space}{r['Отчество'].strip()}, {r['Курс']} курс" for r in records if
                     r['Комната'] == room]
        msg = f"Ваша комната: {room}\n\nВ ней проживают:\n" + "\n".join(neighbors)
    elif room:
        neighbors = [
            f"{r['Фамилия']} {r['Имя']}{mini_space}{r['Отчество'].strip()}, {r['Курс']} курс ({'правая комната)' if r['Комната'][-1] == 'п' else 'левая комната)'}"
            for r in records if r['Комната'][:-1] == room[:-1]]
        msg = f"Ваша комната: {room}\n\nВ блоке проживают:\n" + "\n".join(neighbors)
    else:
        await update.message.reply_text(
            f"Человек с такими ФИО не найден, пожалуйста, проверь данные и начни заново.\n\nВы ввели: {last} {first}{mini_space}{second} {bd}",
            reply_markup=ReplyKeyboardMarkup([['Начать заново']], one_time_keyboard=True, resize_keyboard=True))
        return START

    final_message = msg + (f"{global_comment}") + (
        "\n\nВ дальнейшем ты сможешь использовать этого бота только для обновления информации о себе. Удачного заселения!\n\n"
        "По всем вопросам обращайся в сообщения группы Студкома мехмата: vk.com/studcom_mm")
    await update.message.reply_text(final_message, reply_markup=ReplyKeyboardMarkup([['Обновить']], resize_keyboard=True, one_time_keyboard=True), parse_mode='HTML')

    if is_new_user:
        users.append_row([
            str(update.effective_user.id),
            update.effective_user.username,
            last, first, second, bd, 'OK'
        ])

    return ConversationHandler.END


async def start(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    all_data_records = users.get_all_records()
    user_record = None
    for rec in all_data_records:
        if str(rec.get('tg-id')) == user_id:
            user_record = rec
            break

    if user_record:
        if user_record.get('Status') == 'OK':
            return await find_info(update, context, user_record['Фамилия'], user_record['Имя'],
                                   user_record.get('Отчество', ''), user_record['Дата рождения'])
        else:
            await update.message.reply_text(
                "Доступ к боту ограничен, так как он предназначен для запроса информации <u><b>только</b></u> о себе.\n\n"
                "Если ты уверен, что это ошибка, пожалуйста, напиши в сообщения группы Студкома мехмата: vk.com/studcom_mm",
                reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
        return ConversationHandler.END

    await update.message.reply_text('Внимание! Этот бот предназначен для запроса информации <u><b>только</b></u> о себе.\n\nЕсли ты согласен с условиями использования бота, нажми «Принимаю», чтобы продолжить.',
                                    reply_markup=ReplyKeyboardMarkup([['Принимаю']], one_time_keyboard=True,
                                                                     resize_keyboard=True), parse_mode='HTML')
    return RULES

async def rules(update: Update, context: CallbackContext) -> int:
    text = update.message.text

    if text == 'Принимаю' or text == 'принимаю':
        await update.message.reply_text('Введи свою фамилию с большой буквы (пример: Иванов):',
                                        reply_markup=ReplyKeyboardRemove())
        return LAST_NAME
    else:
        await update.message.reply_text('Чтобы продолжить, необходимо принять условия использования бота.\n\nНажми/введи «Принимаю» для подтверждения твоего согласия.',
                                        reply_markup=ReplyKeyboardMarkup([['Принимаю']], one_time_keyboard=True,
                                                                         resize_keyboard=True))
        return RULES


async def repeat(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Введи свою фамилию с большой буквы (пример: Иванов):',
                                    reply_markup=ReplyKeyboardRemove())
    return LAST_NAME


async def last_name(update: Update, context: CallbackContext) -> int:
    text = update.message.text.replace("ё", "е").replace("Ё", "Е")
    if text == 'Начать заново':
        await update.message.reply_text('Введи свою фамилию с большой буквы (пример: Иванов):',
                                        reply_markup=ReplyKeyboardRemove())
        return LAST_NAME

    context.user_data['last_name'] = text
    await update.message.reply_text('Введи свое имя с большой буквы (пример: Иван):',
                                    reply_markup=ReplyKeyboardMarkup([['Начать заново']], one_time_keyboard=True,
                                                                     resize_keyboard=True))
    return FIRST_NAME


async def first_name(update: Update, context: CallbackContext) -> int:
    text = update.message.text.replace("ё", "е").replace("Ё", "Е")
    if text == 'Начать заново':
        await update.message.reply_text('Введи свою фамилию с большой буквы (пример: Иванов):',
                                        reply_markup=ReplyKeyboardRemove())
        return LAST_NAME

    context.user_data['first_name'] = text
    await update.message.reply_text(
        'Введи свое отчество с большой буквы (если есть, иначе нажмите Пропустить) (пример: Иванович):',
        reply_markup=ReplyKeyboardMarkup([['Пропустить'], ['Начать заново']], one_time_keyboard=True,
                                         resize_keyboard=True))
    return SECOND_NAME


async def second_name(update: Update, context: CallbackContext) -> int:
    text = update.message.text.replace("ё", "е").replace("Ё", "Е")
    if text == 'Начать заново':
        await update.message.reply_text('Введи свою фамилию с большой буквы (пример: Иванов):',
                                        reply_markup=ReplyKeyboardRemove())
        return LAST_NAME

    context.user_data['second_name'] = text if text != 'Пропустить' else ''
    await update.message.reply_text('Введи свою дату рождения в формате ДД.ММ.ГГГГ (пример: 31.01.2000):',
                                    reply_markup=ReplyKeyboardMarkup([['Начать заново']], one_time_keyboard=True,
                                                                     resize_keyboard=True))
    return BIRTH_DATE


async def birth_date(update: Update, context: CallbackContext) -> int:
    birth_date_text = update.message.text
    if birth_date_text == 'Начать заново':
        await update.message.reply_text('Введи свою фамилию с большой буквы (пример: Иванов):',
                                        reply_markup=ReplyKeyboardRemove())
        return LAST_NAME

    try:
        datetime.strptime(birth_date_text, '%d.%m.%Y')
    except ValueError:
        await update.message.reply_text(
            'Дата рождения должна быть в формате ДД.ММ.ГГГГ. Пожалуйста, введи заново (пример: 31.01.2000):',
            reply_markup=ReplyKeyboardMarkup([['Начать заново']], one_time_keyboard=True,
                                             resize_keyboard=True))
        return BIRTH_DATE
    context.user_data['birth_date'] = datetime.strptime(birth_date_text, '%d.%m.%Y').strftime('%d.%m.%Y')

    user_data = context.user_data

    is_claimed_by_other = any(
        r.get('Фамилия') == user_data['last_name'] and
        r.get('Имя') == user_data['first_name'] and
        r.get('Отчество', '') == user_data.get('second_name', '') and
        r.get('Дата рождения') == user_data['birth_date'] and
        r.get('tg-id') != str(update.effective_user.id) and
        r.get('Status') == 'OK'
        for r in users.get_all_records()
    )

    if is_claimed_by_other:
        await update.message.reply_text(
            "Доступ к боту ограничен, так как он предназначен для запроса информации <u><b>только</b></u> о себе.\n\n"
            "Если ты уверен, что это ошибка, пожалуйста, напиши в сообщения группы Студкома мехмата: vk.com/studcom_mm",
            reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')

        users.append_row([
            str(update.effective_user.id), update.effective_user.username,
            user_data['last_name'], user_data['first_name'], user_data.get('second_name', ''),
            user_data['birth_date'], 'ERROR'
        ])
        return ConversationHandler.END
    else:
        return await find_info(update, context, user_data['last_name'], user_data['first_name'],
                               user_data.get('second_name', ''), user_data['birth_date'], is_new_user=True)


async def handler(update: Update, context: CallbackContext) -> int:
    logger.info(f"Fallback handler activated for user {update.effective_user.id}")
    await update.message.reply_text('Этот сервис можно использовать только один раз.',
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token('TOKEN').build()
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^Обновить$'), start),
            MessageHandler(filters.Regex('^обновить$'), start)
        ],
        states={
            START: [MessageHandler(filters.TEXT & ~filters.COMMAND, repeat)],
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, first_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, last_name)],
            SECOND_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, second_name)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, birth_date)],
            RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, rules)]
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, handler)]
    )
    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == '__main__':
    main()