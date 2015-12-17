# -*- coding: utf-8 -*-

import datetime
import json
from app.celery import app, get_tasks_logger


@app.task
def send_order_to_users(order_id, full_description=False):
    from orders_manager.models import Order
    from orders_manager.google_apis import GoogleApiHandler

    logger = get_tasks_logger()
    order = None

    try:
        google_api_handler = GoogleApiHandler()
        order = Order.objects.get(id=order_id)

        def gen_event_desc():
            desc = 'Название программы: %s.\n' % (order.program.title or '-')
            if full_description:
                desc += 'Заказчик: %s (тел. %s)\n' % (
                    order.client.name, order.client.phone)
                desc += 'Ребенок(дети): %s\n' % ', '.join(
                    ['%s (%s)' % (ch.name, ch.verbose_age()) for ch in
                     order.client_children.all()]
                )
                desc += 'Место проведения: %s\n' % order.celebrate_place

                a = json.loads(order.address)

                desc += 'Адрес: %s, ул.%s, д.%s, кв.%s, доп.инф.: %s\n' % (
                    a['city'], a['street'], a['house'], a['apartment'], a['details']
                )
                desc += 'Цена: %s\n' % order.total_price_with_discounts
            return desc

        date_str = '{0} {1}'.format(order.celebrate_date, order.celebrate_time)
        event_start = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        event_duration = int(order.duration)
        event_end = event_start + datetime.timedelta(0, event_duration * 60)
        description = gen_event_desc()
        event_start = event_start.isoformat()
        event_end = event_end.isoformat()

        logger.debug('Sending order \'%s\' start \'%s\'' % (order.program.title,
                                                            event_start))

        for program_executor in order.program_executors.all():
            summary = order.program.title
            try:
                google_api_handler.send_event_to_user_calendar(
                    program_executor.user, order.hex_id(), event_start, event_end,
                    summary, description)
            except ValueError as ex:
                msg_txt = ex.args[0]
                if 'has no credentials' not in msg_txt:
                    raise
                else:
                    logger.warning(msg_txt)

        for service_to_executors in order.additional_services_executors.all():
            summary = ''

            if (service_to_executors.executor_id in
                    [i.user.id for i in order.program_executors.all()]):
                summary = '%s | ' % order.program.title

            summary += service_to_executors.additional_service.title

            try:
                google_api_handler.send_event_to_user_calendar(
                    service_to_executors.executor, order.hex_id(), event_start,
                    event_end, summary, description)
            except ValueError as ex:
                msg_txt = ex.args[0]
                if 'has no credentials' not in msg_txt:
                    raise
                else:
                    logger.warning(msg_txt)
    except Exception as ex:
        logger.error(ex.args[0])

    return order
