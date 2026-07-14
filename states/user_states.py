from aiogram.fsm.state import StatesGroup, State


class PaymentStates(StatesGroup):
    waiting_for_card_receipt = State()
    waiting_for_crypto_receipt = State()


class AdminPaymentStates(StatesGroup):
    waiting_for_delivery = State()
    waiting_for_reject_reason = State()


class AdminServiceStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_service_type = State()
    waiting_for_service_name = State()
    waiting_for_service_description = State()

    waiting_for_plan_service_id = State()
    waiting_for_plan_title = State()
    waiting_for_plan_price = State()
    waiting_for_plan_duration = State()

    waiting_for_edit_service_id = State()
    waiting_for_edit_service_name = State()
    waiting_for_edit_service_description = State()

    waiting_for_toggle_service_id = State()

    waiting_for_edit_plan_id = State()
    waiting_for_edit_plan_title = State()
    waiting_for_edit_plan_price = State()
    waiting_for_edit_plan_duration = State()

    waiting_for_toggle_plan_id = State()


class DiscountStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_amount = State()
    waiting_for_max_uses = State()
    waiting_for_expire_hours = State()
    waiting_for_edit_value = State()


class UserDiscountStates(StatesGroup):
    waiting_for_discount_code = State()


class TicketStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_message = State()


class AdminTicketStates(StatesGroup):
    waiting_for_reply = State()


class ContentStates(StatesGroup):
    waiting_for_content_text = State()


class AdminBroadcastStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_blacklist = State()
    waiting_for_message = State()


class AdminFAQStates(StatesGroup):
    waiting_for_question = State()
    waiting_for_answer = State()
    waiting_for_edit_id = State()
    waiting_for_edit_question = State()
    waiting_for_edit_answer = State()
    waiting_for_delete_id = State()

class StarlinkOrderStates(StatesGroup):
    waiting_for_volume_gb = State()
