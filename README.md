# Ivideon Integration для Home Assistant

Интеграция для мониторинга баланса и платежей в Ivideon Cloud Camera Service.

## Возможности

- Мониторинг баланса аккаунта (общий, реальный, бонусный)
- Отслеживание даты следующего платежа
- Информация о сумме следующего платежа
- Количество камер
- Детальная информация о каждой камере и тарифах

## Сенсоры

После установки создаются следующие сенсоры:

### Основные сенсоры:
- **Balance** - Общий баланс аккаунта
- **Next Payment Date** - Дата следующего платежа
- **Next Payment Amount** - Сумма следующего платежа

### Сенсоры камер (создаются автоматически):
- **sensor.ivideon_1, sensor.ivideon_2, sensor.ivideon_3...** - по одному сенсору на камеру
  - Entity ID: стабильный, на основе индекса (`sensor.ivideon_1`)
  - Friendly Name: название камеры ("Ворота в арке", "Входная дверь")
  - State: "оплачен до 13 января 2026 г."
  - Атрибуты:
    - `due_date` - Дата окончания (DD.MM.YYYY)
    - `message` - Умное сообщение о необходимости оплаты
    - `days_left` - Количество дней до окончания
    - `price` - Стоимость тарифа
    - `camera_name` - Название камеры
    - `camera_id` - ID камеры
    - `tariff_name` - Название тарифа
    - И другие данные о камере

### Диагностические сенсоры:
- **Real Balance** - Реальный баланс (без бонусов)
- **Bonus Balance** - Бонусный баланс
- **Cameras Count** - Количество камер

## Установка

### Вариант 1: Через HACS (рекомендуется)

1. Откройте HACS в Home Assistant
2. Перейдите в раздел "Integrations"
3. Нажмите на три точки в правом верхнем углу
4. Выберите "Custom repositories"
5. Добавьте URL репозитория и выберите категорию "Integration"
6. Найдите "Ivideon" и нажмите "Download"
7. Перезапустите Home Assistant

### Вариант 2: Вручную

1. Скопируйте папку `custom_components/ivideon` в папку `custom_components` вашего Home Assistant
2. Перезапустите Home Assistant

## Настройка

1. Перейдите в **Settings** → **Devices & Services**
2. Нажмите **+ Add Integration**
3. Найдите и выберите **Ivideon**
4. Введите ваш email и пароль от аккаунта Ivideon
5. Укажите интервал обновления данных в минутах (по умолчанию 60 минут)
6. Нажмите **Submit**

## Изменение настроек

Вы можете изменить учетные данные или интервал обновления в любое время:

1. Перейдите в **Settings** → **Devices & Services**
2. Найдите карточку **Ivideon**
3. Нажмите на три точки (⋮) → **Reconfigure**
4. Обновите нужные параметры:
   - Email и пароль (если изменились)
   - Интервал обновления (от 1 до 1440 минут)
5. Нажмите **Submit**

Интеграция автоматически перезагрузится с новыми настройками.
   - Минимум: 1 минута
   - Максимум: 1440 минут (24 часа)
   - Рекомендуется: 60 минут (данные обновляются не так часто)
6. Нажмите **Submit**

### Изменение настроек (реконфигурация)

Вы можете изменить настройки существующей интеграции:

1. Перейдите в **Settings** → **Devices & Services**
2. Найдите интеграцию **Ivideon**
3. Нажмите на три точки → **Reconfigure**
4. Измените email, пароль или интервал обновления
5. Нажмите **Submit**

Интеграция автоматически перезагрузится с новыми настройками.

## Использование

### Просмотр данных

После настройки все сенсоры будут доступны в Home Assistant. Вы можете добавить их на dashboard:

```yaml
type: entities
title: Ivideon
entities:
  - entity: sensor.balance
  - entity: sensor.next_payment_date
  - entity: sensor.next_payment_amount
  - entity: sensor.cameras_count
```

### Просмотр камер

Для каждой камеры создается отдельный сенсор:

```yaml
type: entities
title: Ivideon Камеры
entities:
  - sensor.ivideon_1
    secondary_info: last-updated
  - sensor.ivideon_2
    secondary_info: last-updated
  - sensor.ivideon_3
    secondary_info: last-updated
```

Friendly name каждого сенсора автоматически берется из названия камеры:
- `sensor.ivideon_1` → "Ворота в арке"
- `sensor.ivideon_2` → "Входная дверь"
- `sensor.ivideon_3` → "Парковка"

Карточка с детальной информацией:

```yaml
type: markdown
title: Камера
content: |
  **{{ state_attr('sensor.ivideon_1', 'camera_name') }}**
  
  {{ state_attr('sensor.ivideon_1', 'message') }}
  
  💰 Стоимость: {{ state_attr('sensor.ivideon_1', 'price') }} ₽
  📅 Оплачен до: {{ state_attr('sensor.ivideon_1', 'due_date') }}
  ⏰ Осталось дней: {{ state_attr('sensor.ivideon_1', 'days_left') }}
```

### Автоматизации

Пример автоматизации для уведомления о низком балансе:

```yaml
automation:
  - alias: "Ivideon: Низкий баланс"
    trigger:
      - platform: numeric_state
        entity_id: sensor.balance
        below: 500
    action:
      - service: notify.mobile_app
        data:
          title: "Низкий баланс Ivideon"
          message: "Баланс: {{ states('sensor.balance') }} ₽"
```

Пример уведомления за 3 дня до платежа:

```yaml
automation:
  - alias: "Ivideon: Скоро платёж"
    trigger:
      - platform: template
        value_template: >
          {{ (as_timestamp(states('sensor.next_payment_date')) - 
              as_timestamp(now())) / 86400 < 3 }}
    action:
      - service: notify.mobile_app
        data:
          title: "Ivideon: Скоро платёж"
          message: >
            Дата: {{ states('sensor.next_payment_date') }}
            Сумма: {{ states('sensor.next_payment_amount') }} ₽
```

Уведомление об оплате конкретной камеры (за 3 дня):

```yaml
automation:
  - alias: "Ivideon: Напоминание об оплате камеры"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ivideon_1
        attribute: days_left
        below: 4
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.ivideon_1', 'days_left') > 0 }}"
    action:
      - service: notify.mobile_app
        data:
          title: "📹 {{ state_attr('sensor.ivideon_1', 'camera_name') }}"
          message: "{{ state_attr('sensor.ivideon_1', 'message') }}"
          data:
            priority: high
```

Проверка всех камер и уведомление о тех, которые скоро нужно оплатить:

```yaml
automation:
  - alias: "Ivideon: Ежедневная проверка камер"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - repeat:
          count: "{{ states('sensor.cameras_count') | int }}"
          sequence:
            - variables:
                camera_sensor: "sensor.ivideon_{{ repeat.index }}"
            - condition: template
              value_template: >
                {{ state_attr(camera_sensor, 'days_left') is not none and
                   state_attr(camera_sensor, 'days_left') <= 3 and
                   state_attr(camera_sensor, 'days_left') > 0 }}
            - service: notify.mobile_app
              data:
                title: "📹 Скоро окончание оплаты"
                message: "{{ state_attr(camera_sensor, 'message') }}"
```

### Атрибуты сенсоров

#### Balance
- `user_id` - ID пользователя
- `success` - Статус успешности запроса
- `balance` - Общий баланс (в копейках)
- `real_balance` - Реальный баланс (в копейках)
- `bonus_balance` - Бонусный баланс (в копейках)
- `currency` - Валюта
- `credit_limit` - Кредитный лимит
- `locked_balance` - Заблокированный баланс
- `last_updated` - Время последнего обновления

#### Ivideon 1, 2, 3... (камерные сенсоры)
- `camera_name` - Название камеры
- `camera_id` - ID камеры
- `due_date` - Дата окончания (DD.MM.YYYY)
- `message` - Сообщение о необходимости оплаты
- `days_left` - Количество дней до окончания
- `price` - Стоимость тарифа
- `currency` - Валюта
- `tariff_name` - Название тарифа
- `tariff_id` - ID тарифа
- `period` - Период оплаты
- `payment_type` - Тип оплаты
- `active` - Активна ли камера
- `expired` - Истёк ли тариф
- `start_date` - Дата начала
- `expires_date` - Дата окончания (ISO)
- `last_updated` - Время последнего обновления

#### Next Payment Amount
- `cameras` - Список камер для оплаты:
  - `name` - Название камеры
  - `tariff` - Название тарифа
  - `cost` - Стоимость

#### Cameras Count
- `cameras` - Список всех камер:
  - `name` - Название
  - `id` - ID камеры
  - `tariff` - Тариф
  - `expires` - Дата окончания
  - `cost` - Стоимость
  - `active` - Активна ли
  - `expired` - Истёк ли тариф

## Обновление данных

Интервал обновления данных настраивается при добавлении интеграции (по умолчанию 60 минут). 

Вы можете изменить интервал обновления в любой момент:
- Перейдите в **Settings** → **Devices & Services**
- Найдите **Ivideon** → три точки → **Reconfigure**
- Измените интервал обновления (от 1 до 1440 минут)

**Рекомендации:**
- Для обычного использования: 60-120 минут
- Для активного мониторинга: 15-30 минут
- Для редких проверок: 360-1440 минут

Учтите, что слишком частые запросы могут привести к ограничениям со стороны API.

## Требования

- Home Assistant 2023.1 или новее
- Аккаунт Ivideon с доступом к API

## Безопасность

- Логин и пароль хранятся в зашифрованном виде в Home Assistant
- Токены доступа обновляются автоматически
- Используется OAuth2 для безопасной аутентификации

## Поддержка

При возникновении проблем:

1. Проверьте логи Home Assistant
2. Убедитесь, что логин и пароль указаны правильно
3. Проверьте, что у вас есть доступ к Ivideon API

## Лицензия

MIT License

## Changelog

### 1.2.3
- Исправлено: Автоматическая конвертация валюты RUR → RUB во всех сенсорах и атрибутах
- Все значения currency теперь показывают "RUB" вместо "RUR"

### 1.2.2
- Entity ID камерных сенсоров: стабильные sensor.ivideon_1, sensor.ivideon_2, ...
- Friendly Name автоматически берется из названия камеры
- Entity ID не изменится при переименовании камеры

### 1.2.1
- Исправлено: Имена камерных сенсоров теперь используют название камеры
- Исправлено: sensor.balance корректно отображает значение
- Добавлены все атрибуты баланса из API response

### 1.2.0
- Добавлены индивидуальные сенсоры для каждой камеры
- Умные уведомления о необходимости оплаты для каждой камеры
- Форматирование дат на русском языке
- Подробные атрибуты для каждого камерного сенсора

### 1.1.0
- Добавлена настройка интервала обновления через UI (от 1 до 1440 минут)
- Добавлена возможность реконфигурации интеграции
- Интервал по умолчанию: 60 минут

### 1.0.0
- Первый релиз
- Мониторинг баланса
- Информация о следующем платеже
- Список камер и тарифов
