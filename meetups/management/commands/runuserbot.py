import asyncio
import logging
from datetime import datetime

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from django.core.management.base import BaseCommand
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from django.db.models import Count
from aiogram.types.message import ContentTypes

from meetups.management.commands.texts import about_bot
from meetups.models import (
    Client,
    Event,
    Presentation,
    Question,
    Visitor,
    Likes,
    Organizer, Donate
)
from asgiref.sync import sync_to_async
from conf import settings
from meetups.management.commands import admin_handlers
from meetups.management.commands.user_keyboards import (
    get_user_main_keyboard,
    get_event_schedule_keyboard,
    get_current_presentation_keyboard,
    get_current_presentation_question_keyboard,
    get_question_main_menu_keyboard,
    get_cancel_keyboard,
    get_just_main_menu_keyboard, get_presentation_annotation_keyboard, get_show_my_events_keyboard,
    get_question_contacts_keyboard, get_donate_keyboard, get_my_presentations_keyboard,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s',
)

logger = logging.getLogger('UserBot')

storage = MemoryStorage()
bot = Bot(settings.TG_TOKEN_API)
dp = Dispatcher(bot=bot, storage=storage)

user_register_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='Зарегистрироваться', callback_data='user_register'),
    ],
])


class ClientRegisterFSM(StatesGroup):
    choose_event = State()
    personal_info = State()


class ClientAskQuestionFSM(StatesGroup):
    enter_question = State()


class DonateFSM(StatesGroup):
    enter_donate_amount = State()
    await_pre_checkout = State()
    successful_payment = State()


@dp.message_handler(commands=['start'])
async def start_command(message: types.Message) -> None:
    client, created = await sync_to_async(Client.objects.get_or_create)(
        chat_id=message.from_user.id,
    )
    if created or not client.first_name or not client.last_name:
        await message.answer('🤖 Добро пожаловать в чат-бот\n<b>Python Meetups!</b>\n\n'
                             'Я помогу вам получить 💪 максимум от каждого события.\n'
                             'С моей помощью вы можете:\n\n'
                             '✅ быстро <b>зарегистрироваться</b> на мероприятие,\n\n'
                             '📖 легко ознакомиться с <b>программой</b>,\n\n'
                             '❓<b>задавать вопросы</b> докладчикам\n\n'
                             '💰а также поддержать нас, отправив донат.\n\n'
                             'Если вы выступаете на мероприятии, то вы также сможете '
                             '👀 посмотреть вопросы от зрителей вашей презентации\n\n'
                             '🎫 Чтобы начать работу с ботом необходимо зарегистрироваться.',
                            parse_mode='HTML',
                            reply_markup=user_register_keyboard,
                            )
    else:
        user_main_keyboard = await get_user_main_keyboard(client)
        await message.answer('🤖 ГЛАВНОЕ МЕНЮ:',
                             parse_mode='HTML',
                             reply_markup=user_main_keyboard,
                             )


@dp.callback_query_handler(lambda callback_query: callback_query.data == 'user_register', state='*')
async def user_register_handler(callback: types.CallbackQuery) -> None:
    await ClientRegisterFSM.choose_event.set()
    events = await sync_to_async(Event.objects.all)()
    inline_keyboard = []
    async for event in events:
        when_info = f'{event.date.strftime("%d.%m")} {event.start_time.strftime("%H:%M")}'
        name_info = f'{event.name}'
        event_keyboard=[[
            InlineKeyboardButton(text=name_info, callback_data=f'event_{event.id}')
        ],
        [
            InlineKeyboardButton(text=when_info, callback_data=f'event_{event.id}'),
            InlineKeyboardButton(text='✅', callback_data=f'event_choose_{event.id}'),
            InlineKeyboardButton(text='❔', callback_data=f'event_about_{event.id}'),
        ]]
        inline_keyboard += event_keyboard
    events_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await callback.message.edit_text('Пожалуйста, выберите <b>мероприятие</b>, которое Вас интересует, нажав галочку - ✅\n\n'
                                     'Вы можете также посмотреть описание мероприятия, нажав на знак вопроса -❔',
                                     parse_mode='HTML',
                                     reply_markup=events_keyboard,
                                    )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('event_'),
                           state=ClientRegisterFSM.choose_event)
async def event_choose_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    event_id = callback.data.split('_')[-1]
    event = await sync_to_async(Event.objects.get)(id=event_id)
    if callback.data.startswith('event_about_'):
        event_register_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text='Регистрация', callback_data=f'event_choose_{event.id}'),
                InlineKeyboardButton(text='Назад', callback_data='user_register'),
            ],
        ])
        await callback.message.edit_text(event.description,
                                         parse_mode='HTML',
                                         reply_markup=event_register_keyboard,
                                         )
    if callback.data.startswith('event_choose_'):
        async with state.proxy() as data:
            data['event'] = event

        await ClientRegisterFSM.next()
        await callback.message.answer(f'Вы выбрали мероприятие: <b>{event.name}</b>\n'
                                      'Для продолжения регистрации введите Ваше имя и '
                                      'фамилию в формате: <b>Имя Фамилия</b>',
                                      parse_mode='HTML',
                                      )


@dp.callback_query_handler(lambda callback_query: callback_query.data == 'show_schedule', state='*')
async def show_schedule_handler(callback: types.CallbackQuery) -> None:
    today = datetime.today()
    now = datetime.now()
    current_event = await sync_to_async(Event.objects.filter(date=today, start_time__lte=now.time()).first)()
    await callback.message.edit_text(f'<b>{current_event.name}</b>\n\n'
                                     f'<em>Нажмите на название доклада, чтобы '
                                     f'📖 прочитать о нем подробнее</em>\n\n'
                                     f'🕓 РАСПИСАНИЕ НА СЕГОДНЯ:',
                                     parse_mode='HTML',
                                     reply_markup=await get_event_schedule_keyboard(current_event),
                                     )


@dp.message_handler(state=ClientRegisterFSM.personal_info)
async def user_register_personal_info_handler(message: types.Message, state: FSMContext) -> None:
    if message.text.count(' ') != 1:
        await message.answer('Неверный формат ввода. Попробуйте еще раз.\n'
                             'Введите ваше имя и фамилию в формате: <b>Имя Фамилия</b>',
                             parse_mode='HTML',
                             )
        return
    first_name, last_name = message.text.split()
    logger.info(f'first_name: {first_name}, last_name: {last_name}')
    client, _ = await sync_to_async(Client.objects.get_or_create)(chat_id=message.from_user.id)
    client.first_name = first_name
    client.last_name = last_name
    await sync_to_async(client.save)()
    async with state.proxy() as data:
        event = data['event']
    await sync_to_async(Visitor.objects.get_or_create)(
        client=client,
        event=event,
    )
    await bot.send_message(client.chat_id,
                           f'{client.first_name} {client.last_name}, Вы успешно зарегистрированы!',
                           parse_mode='HTML',
                           reply_markup=await get_user_main_keyboard(client)
                           )
    await state.finish()


@dp.callback_query_handler(lambda callback_query: callback_query.data == 'show_current_presentation', state='*')
async def show_current_presentation_handler(callback: types.CallbackQuery) -> None:
    today = datetime.today()
    now = datetime.now()
    current_event = await sync_to_async(Event.objects.filter(date=today, start_time__lte=now.time()).first)()
    if current_event:
        current_presentation = await sync_to_async(Presentation.objects.filter(
            event=current_event,
            start_time__lte=now.time(),
            is_finished=False,
        ).select_related('speaker').first)()
    speaker_chat_id = current_presentation.speaker.chat_id
    speaker = int(speaker_chat_id) == int(callback.from_user.id)
    logger.info(f'speaker: {speaker}')
    texts = {
        'True': f'CЕЙЧАС ИДЕТ ВАШ ДОКЛАД:\n\n'
               f'<b>{current_presentation.name}</b>\n\n'
               f'<b>Докладчик</b>\n'
               f'{current_presentation.speaker.first_name} {current_presentation.speaker.last_name}\n\n'
               f'<em>Здесь вы можете посмотреть вопросы'
               f' или завершить доклад</em>',
        'False': f'CЕЙЧАС ИДЕТ ДОКЛАД:\n\n'
               f'<b>{current_presentation.name}</b>\n\n'
               f'<b>Описание:</b>\n'
               f'{current_presentation.annotation}\n\n'
               f'<b>Докладчик</b>\n'
               f'{current_presentation.speaker.first_name} {current_presentation.speaker.last_name}\n\n'\
               f'<em>Здесь вы можете задать вопрос докладчику'
               f' или посмотреть заданные ранее вопросы и'
               f'  поддержать интересные вам, нажав на 👍</em>\n\n'
    }
    await callback.message.answer(texts[str(speaker)],
                                  parse_mode='HTML',
                                  reply_markup=await get_current_presentation_keyboard(
                                      current_presentation,
                                      speaker,
                                  ),
                                  )

@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('questions_show'), state='*')
async def show_current_presentation_questions_handler(callback: types.CallbackQuery) -> None:
    presentation_id = callback.data.split('_')[-1]
    questions = await sync_to_async(
        Question.objects.filter(
            presentation=presentation_id,
            is_closed=False,
        ).all().select_related('presentation').select_related('client').prefetch_related)('likes')
    presentation = await sync_to_async(
        Presentation.objects.filter(pk=presentation_id).select_related('speaker').first
    )()
    speaker_chat_id = presentation.speaker.chat_id
    speaker = int(speaker_chat_id) == int(callback.from_user.id)
    async for question in questions:
        likes_count = await sync_to_async(question.likes.count)()
        author = int(question.client.chat_id) == int(callback.from_user.id)
        texts = {
            'True': f'<b>Вопрос №{question.question_number}:</b> ✏ 👍 {likes_count}\n'
                    f'--------------------------------------\n'
                    f'{question.text}\n\n',
            'False': f'<b>Вопрос №{question.question_number}:</b> 👍 {likes_count}\n'
                     f'--------------------------------------\n'
                    f'{question.text}\n\n',
        }
        await callback.message.answer(texts[str(author)],
                                      parse_mode='HTML',
                                      reply_markup=await get_current_presentation_question_keyboard(
                                        question,
                                        callback.from_user.id,
                                        speaker,
                                      ),
                                    )
    texts = {
        'True': f'Не забывайте иногда <b>обновлять список вопросов</b>, чтобы не пропустить новые!',
        'False': f'Вы также можете задать свой вопрос или вернуться в главное меню:'
    }
    await callback.message.answer(texts[str(speaker)],
                                  parse_mode='HTML',
                                  reply_markup=await get_question_main_menu_keyboard(
                                      presentation_id,
                                      speaker,
                                  ),
                                  )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('question_ask'), state='*')
async def ask_question_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    presentation_id = callback.data.split('_')[-1]
    await ClientAskQuestionFSM.enter_question.set()
    await callback.message.answer('Введите ваш вопрос:',
                                  parse_mode='HTML',
                                  reply_markup=await get_cancel_keyboard(),
                                  )
    async with state.proxy() as data:
        data['presentation_id'] = presentation_id


@dp.message_handler(state=ClientAskQuestionFSM.enter_question)
async def save_question_handler(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        presentation_id = data['presentation_id']
    presentation = await sync_to_async(
        Presentation.objects.filter(pk=presentation_id).annotate(num_questions=Count('questions')).first
    )()
    question_number = presentation.num_questions + 1
    client = await sync_to_async(Client.objects.get)(chat_id=message.from_user.id)
    await sync_to_async(Question.objects.create)(
        client=client,
        presentation=presentation,
        text=message.text,
        question_number=question_number,
    )

    await message.answer('Ваш вопрос отправлен докладчику!',
                         parse_mode='HTML',
                         reply_markup=await get_user_main_keyboard(client),
                         )
    await state.finish()


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('question_like'), state='*')
async def like_question_handler(callback: types.CallbackQuery) -> None:
    question_id = callback.data.split('_')[-1]
    client = await sync_to_async(Client.objects.get)(chat_id=callback.from_user.id)
    question = await sync_to_async(
        Question.objects.filter(
            pk=question_id,
        ).select_related('presentation').select_related('client').prefetch_related('likes').first)()
    increased_likes_number = await sync_to_async(question.likes.count)() + 1
    exists_user_like = await sync_to_async(Likes.objects.filter(
        client__chat_id=callback.from_user.id,
        question=question,
    ).exists)()
    if exists_user_like:
        await callback.message.edit_text(f'Вы уже поддержали вопрос №{question_id}!',
                                      parse_mode='HTML',
                                      reply_markup=await get_user_main_keyboard(client),
                                      )
        return
    await sync_to_async(Likes.objects.create)(
        client=client,
        question=question,
    )
    await callback.message.edit_text(f'<b>Вопрос №{question.question_number}:</b> 👍 {increased_likes_number}\n\n'
                                     f'{question.text}\n\n',
                                     parse_mode='HTML',
                                     reply_markup=await get_current_presentation_question_keyboard(
                                         question,
                                         callback.from_user.id,
                                         speaker=False,
                                     ),
                                     )

@dp.message_handler(commands=['cancel'], state='*')
async def cancel_handler(message: types.Message, state: FSMContext) -> None:
    await state.finish()
    client = await sync_to_async(Client.objects.get)(chat_id=message.from_user.id)
    await message.answer('🤖 ГЛАВНОЕ МЕНЮ:',
                         parse_mode='HTML',
                         reply_markup=await get_user_main_keyboard(client),
                         )


@dp.callback_query_handler(lambda callback_query: callback_query.data in ['main_menu', 'cancel'], state='*')
async def get_main_menu_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    client = await sync_to_async(Client.objects.get)(chat_id=callback.from_user.id)
    await state.finish()
    await callback.message.edit_text('🤖 ГЛАВНОЕ МЕНЮ:',
                                     parse_mode='HTML',
                                     reply_markup=await get_user_main_keyboard(client),
                                     )


@dp.message_handler(commands=['help'], state='*')
async def cancel_handler(message: types.Message, state: FSMContext) -> None:

    await message.answer(about_bot,
                         parse_mode='HTML',
                         reply_markup=await get_just_main_menu_keyboard(),
                         )


@dp.callback_query_handler(lambda callback_query: callback_query.data == 'about', state='*')
async def get_bot_about_handler(callback: types.CallbackQuery) -> None:

    await callback.message.edit_text(about_bot,
                                     parse_mode='HTML',
                                     reply_markup=await get_just_main_menu_keyboard(),
                                     )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('presentation_annotation'), state='*')
async def get_presentation_annotation_handler(callback: types.CallbackQuery) -> None:
    presentation_id = callback.data.split('_')[-1]
    presentation = await sync_to_async(
        Presentation.objects.filter(pk=presentation_id).select_related('speaker').first
    )()
    text = f'<b>{presentation.name.upper()}</b>\n\n'\
           f'{presentation.annotation}\n\n'\
           f'<b>Докладчик</b>\n'\
           f'{presentation.speaker.first_name} {presentation.speaker.last_name}\n\n'\
           f'<b>Время</b>\n'\
           f'{presentation.start_time.strftime("%H:%M")} - {presentation.end_time.strftime("%H:%M")}'

    await callback.message.edit_text(text,
                                     parse_mode='HTML',
                                     reply_markup=await get_presentation_annotation_keyboard(),
                                     )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('show_my_events'), state='*')
async def get_show_my_events_handler(callback: types.CallbackQuery) -> None:
    today = datetime.today()
    client = await sync_to_async(Client.objects.get)(chat_id=callback.from_user.id)
    user_events_ids = await sync_to_async(
        Client.objects.filter(pk=client.pk, events__date__gte=today).distinct().values_list)('events', flat=True)
    user_events_ids = await sync_to_async(list)(user_events_ids)
    user_events = await sync_to_async(Event.objects.filter)(pk__in=user_events_ids)
    inline_keyboard = []
    async for event in user_events:
        when_info = f'{event.date.strftime("%d.%m")} {event.start_time.strftime("%H:%M")}'
        name_info = f'{event.name}'
        event_keyboard=[[
            InlineKeyboardButton(text=name_info, callback_data=f'event_{event.id}')
        ],
        [
            InlineKeyboardButton(text=when_info, callback_data=f'event_{event.id}'),
            InlineKeyboardButton(text='❔', callback_data=f'event_about_{event.id}'),
        ]]
        inline_keyboard += event_keyboard
    main_menu_keyboard = [
        [
            InlineKeyboardButton(text='Главное меню', callback_data='main_menu'),
        ],
    ]
    inline_keyboard += main_menu_keyboard
    events_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await callback.message.edit_text('Вы можете посмотреть описание мероприятия, нажав на знак вопроса -❔',
                                     parse_mode='HTML',
                                     reply_markup=events_keyboard,
                                    )

@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('event_about'), state='*')
async def get_event_about_handler(callback: types.CallbackQuery) -> None:
    event_id = callback.data.split('_')[-1]
    event = await sync_to_async(Event.objects.get)(id=event_id)
    await callback.message.edit_text(event.description,
                                     parse_mode='HTML',
                                     reply_markup=await get_show_my_events_keyboard(),
                                     )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('question_contacts'), state='*')
async def get_question_contacts_handler(callback: types.CallbackQuery) -> None:
    question_id = callback.data.split('_')[-1]
    question = await sync_to_async(
        Question.objects.filter(id=question_id).select_related('presentation').select_related('client').first
    )()
    likes = await sync_to_async(Likes.objects.filter(question__pk=question_id).select_related)('client')
    presentation = question.presentation
    text = f'{question.text}\n\n'
    async for like in likes:
        text += f'{like.client.first_name} {like.client.last_name}, tg: {like.client.chat_id}\n\n'
    text += f'{question.client.first_name} {question.client.last_name}, tg: {question.client.chat_id}'
    await callback.message.edit_text(text,
                                     parse_mode='HTML',
                                     reply_markup=await get_question_contacts_keyboard(presentation),
                                     )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('presentation_finish'), state='*')
async def get_presentation_finish_handler(callback: types.CallbackQuery) -> None:
    presentation_id = callback.data.split('_')[-1]
    presentation = await sync_to_async(
        Presentation.objects.filter(pk=presentation_id).first
    )()
    presentation.is_finished = True
    await sync_to_async(presentation.save)()
    await callback.message.edit_text('Ваш доклад завершен!',
                                     parse_mode='HTML',
                                     reply_markup=await get_just_main_menu_keyboard(),
                                     )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('pay_'),
                           state=DonateFSM.enter_donate_amount)
async def get_donate_callback_handler(callback: types.CallbackQuery) -> None:
    donate_sum = int(callback.data.split('_')[-1])
    prices = [LabeledPrice(label='Поддержка PythonMeetups', amount=donate_sum * 100)]
    user_id = callback.from_user.id
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title='Добровольное пожертвование',
        description='Поддержка PythonMeetups',
        provider_token=settings.YOO_KASSA_PROVIDER_TOKEN,
        currency='RUB',
        prices=prices,
        payload='user_id_{}'.format(user_id),
    )
    await DonateFSM.next()


@dp.message_handler(state=DonateFSM.enter_donate_amount)
async def get_donate_message_handler(message: types.Message) -> None:
    try:
        donate_sum = int(message.text)
    except ValueError:
        await message.answer('Пожалуйста, введите число:')
        return
    else:
        prices = [LabeledPrice(label='Поддержка PythonMeetups', amount=donate_sum * 100)]
        user_id = message.from_user.id
        await bot.send_invoice(
            chat_id=message.from_user.id,
            title='Добровольное пожертвование',
            description='Поддержка PythonMeetups',
            provider_token=settings.YOO_KASSA_PROVIDER_TOKEN,
            currency='RUB',
            prices=prices,
            payload='user_id_{}'.format(user_id),
        )
        await DonateFSM.next()


@dp.pre_checkout_query_handler(state=DonateFSM.await_pre_checkout)
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery, state: FSMContext):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    await state.finish()


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('donate'), state='*')
async def enter_donate_sum_handler(callback: types.CallbackQuery) -> None:
    await DonateFSM.enter_donate_amount.set()
    await callback.message.edit_text('Спасибо, что решили нас поддержать!\n'
                                     'Пожалуйста, выберите, сумму доната '
                                     'или введите ее вручную в ответном сообщении.',
                                     parse_mode='HTML',
                                     reply_markup=await get_donate_keyboard(),
                                     )

@dp.message_handler(content_types=ContentTypes.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    client = await sync_to_async(Client.objects.get)(chat_id=message.from_user.id)
    today = datetime.today()
    now = datetime.now()
    current_event = await sync_to_async(Event.objects.filter(date=today, start_time__lte=now.time()).first)()
    total_amount = message.successful_payment.total_amount / 100
    await sync_to_async(Donate.objects.create)(
        client=client,
        sum=total_amount,
        event=current_event,
    )
    await bot.send_message(chat_id=message.from_user.id,
                           text=f'{total_amount} руб. успешно зачислены!\n\n'
                                f'Ваша поддержка очень важна для нас!\n'
                                f'❤️ Спасибо!',
                           parse_mode='HTML',
                           reply_markup=await get_just_main_menu_keyboard(),
                           )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('question_close'), state='*')
async def get_presentation_finish_handler(callback: types.CallbackQuery) -> None:
    question_id = callback.data.split('_')[-1]
    question = await sync_to_async(
        Question.objects.filter(pk=question_id).first
    )()
    question.is_closed = True
    await sync_to_async(question.save)()
    await callback.message.edit_text('Вопрос закрыт!',
                                     parse_mode='HTML',
                                     )


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith('question_close'), state='*')
async def get_presentation_finish_handler(callback: types.CallbackQuery) -> None:
    question_id = callback.data.split('_')[-1]
    question = await sync_to_async(
        Question.objects.filter(pk=question_id).first
    )()
    question.is_closed = True
    await sync_to_async(question.save)()
    await callback.message.edit_text('Вопрос закрыт!',
                                     parse_mode='HTML',
                                     )

@dp.callback_query_handler(lambda callback_query: callback_query.data == 'show_my_presentations', state='*')
async def show_my_presentations_handler(callback: types.CallbackQuery) -> None:
    client = await sync_to_async(Client.objects.get)(chat_id=callback.from_user.id)
    await callback.message.edit_text('СПИСОК ВАШИХ ДОКЛАДОВ:',
                                     parse_mode='HTML',
                                     reply_markup=await get_my_presentations_keyboard(client),
                                     )


async def set_commands(bot: Bot):
    commands = [
            types.BotCommand(
                command="/start",
                description="Начало",
            ),
            types.BotCommand(
                command="/admin",
                description="Меню организатора",
            ),
            types.BotCommand(
                command="/help",
                description="Справка по работе бота",
            ),
            types.BotCommand(
                command="/cancel",
                description="Отмена текущего действия, возврат в главное меню",
            ),
        ]
    await bot.set_my_commands(commands)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        executor.start_polling(dp, skip_updates=True)
