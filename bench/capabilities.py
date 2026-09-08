"""
Capability tags for every AgentDojo tool, per suite.

Rules used:
  UNTRUSTED_INPUT  the tool returns content that can carry an injection
                   (emails, files, calendar descriptions, reviews, web pages, slack messages, transactions)
  PRIVATE_DATA     the tool reads the user's own data (inbox, files, contacts, balance, user info, calendar)
  EXTERNAL_ACTION  the tool changes state or communicates outside the session
                   (send, share, reserve, transfer, post, invite, delete, create, update)

A tool can carry more than one. In AgentDojo the user's inbox is both private and untrusted:
that is the realistic case, and it is why strict mode costs utility.
"""
from flightmode import Capability as C

U, P, E = C.UNTRUSTED_INPUT, C.PRIVATE_DATA, C.EXTERNAL_ACTION

WORKSPACE = {
    "send_email": {E},
    "delete_email": {E},
    "get_unread_emails": {U, P},
    "get_sent_emails": {P},
    "get_received_emails": {U, P},
    "get_draft_emails": {P},
    "search_emails": {U, P},
    "search_contacts_by_name": {P},
    "search_contacts_by_email": {P},
    "get_current_day": set(),
    "search_calendar_events": {U, P},
    "get_day_calendar_events": {U, P},
    "create_calendar_event": {E},
    "cancel_calendar_event": {E},
    "reschedule_calendar_event": {E},
    "add_calendar_event_participants": {E},
    "append_to_file": {E},
    "search_files_by_filename": {U, P},
    "create_file": {E},
    "delete_file": {E},
    "get_file_by_id": {U, P},
    "list_files": {U, P},
    "share_file": {E},
    "search_files": {U, P},
}

TRAVEL = {
    "get_user_information": {P},
    "get_all_hotels_in_city": {U},
    "get_hotels_prices": {U},
    "get_rating_reviews_for_hotels": {U},
    "get_hotels_address": {U},
    "get_all_restaurants_in_city": {U},
    "get_cuisine_type_for_restaurants": {U},
    "get_restaurants_address": {U},
    "get_rating_reviews_for_restaurants": {U},
    "get_dietary_restrictions_for_all_restaurants": {U},
    "get_contact_information_for_restaurants": {U},
    "get_price_for_restaurants": {U},
    "check_restaurant_opening_hours": {U},
    "get_all_car_rental_companies_in_city": {U},
    "get_car_types_available": {U},
    "get_rating_reviews_for_car_rental": {U},
    "get_car_fuel_options": {U},
    "get_car_rental_address": {U},
    "get_car_price_per_day": {U},
    "create_calendar_event": {E},
    "search_calendar_events": {P},
    "get_day_calendar_events": {P},
    "cancel_calendar_event": {E},
    "reserve_hotel": {E},
    "reserve_car_rental": {E},
    "reserve_restaurant": {E},
    "get_flight_information": {U},
    "send_email": {E},
}

BANKING = {
    "get_iban": {P},
    "send_money": {E},
    "schedule_transaction": {E},
    "update_scheduled_transaction": {E},
    "get_balance": {P},
    "get_most_recent_transactions": {U, P},
    "get_scheduled_transactions": {U, P},
    "read_file": {U, P},
    "get_user_info": {P},
    "update_password": {E},
    "update_user_info": {E},
}

SLACK = {
    "get_channels": {P},
    "add_user_to_channel": {E},
    "read_channel_messages": {U, P},
    "read_inbox": {U, P},
    "send_direct_message": {E},
    "send_channel_message": {E},
    "get_users_in_channel": {P},
    "invite_user_to_slack": {E},
    "remove_user_from_slack": {E},
    "get_webpage": {U, E},
    "post_webpage": {E},
}

SUITES = {"workspace": WORKSPACE, "travel": TRAVEL, "banking": BANKING, "slack": SLACK}
