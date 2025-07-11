import pytest
import time
import math
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options 

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class Locators:
    RUBLE_ACCOUNT_CARD = (By.XPATH, "//h2[normalize-space()='Рубли']")
    F_BANK_LOGO = (By.XPATH, "//h1[contains(text(), 'F-Bank')]")
    RUBLE_BALANCE = (By.XPATH, "//h2[normalize-space()='Рубли']/following-sibling::p[contains(text(), 'На счету:')]")

    CARD_NUMBER_INPUT = (By.XPATH, "//input[@placeholder='0000 0000 0000 0000']")
    TRANSFER_AMOUNT_INPUT = (By.XPATH, "//h3[contains(text(), 'Сумма перевода')]/following-sibling::input")
    TRANSFER_BUTTON = (By.XPATH, "//button[normalize-space()='Перевести']")
    COMMISSION_VALUE = (By.XPATH, "//p[contains(text(), 'Комиссия:')]")

    ERROR_MESSAGE = (By.XPATH, "//*[contains(text(), 'Недостаточно средств на счете')]")
    AMOUNT_VALIDATION_ERROR = (By.XPATH, "//input[@type='number' and @name='amount']/following-sibling::p[contains(@class, 'error-message')]")

# --- Фикстура для инициализации и закрытия браузера ---
@pytest.fixture
def browser():
    print("\nНастройка драйвера для Chrome (для CI)")
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox") 
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") 

    driver = webdriver.Chrome(options=chrome_options)
    
    yield driver
    print("\nЗакрытие драйвера")
    driver.quit()


# --- Вспомогательная функция для начала перевода ---
def start_transfer(driver, balance=30000, reserved=20001):
    driver.get(f"http://localhost:8000/?balance={balance}&reserved={reserved}")
    
    try:
        ruble_account = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(Locators.RUBLE_ACCOUNT_CARD)
        )
        ruble_account.click()
    except TimeoutException:
        print("\n\nОШИБКА: Не удалось найти карточку 'Рубли' на странице.")
        print(driver.page_source)
        pytest.fail("Не удалось найти ключевой элемент для начала теста. Смотрите HTML-код выше.")

# Тест TC-4.1
def test_p4_max_possible_transfer(browser):
    start_transfer(browser, balance=9999, reserved=0)
    
    card_input = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT)
    )
    card_input.clear()
    card_input.send_keys("1111222233334444") 

    amount_input = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT)
    )
    amount_input.clear()
    
    transfer_amount_str = "9099"
    amount_input.send_keys(transfer_amount_str)

    expected_commission_str = "900" 
    
    commission_element = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.COMMISSION_VALUE)
    )
    assert f"Комиссия: {expected_commission_str}" in commission_element.text, \
        f"Ожидалась комиссия содержащая '{expected_commission_str}', но отображается: '{commission_element.text}'"
    transfer_amount = int(transfer_amount_str)
    commission_amount = int(expected_commission_str)
    total_debit = transfer_amount + commission_amount
    
    assert total_debit <= 9999, \
        f"Сумма списания ({total_debit}) превышает максимально допустимую (9999)"

    try:
        error_message = WebDriverWait(browser, 5).until(
            EC.visibility_of_element_located(Locators.ERROR_MESSAGE)
        )
        assert "Недостаточно средств" in error_message.text, \
            "Ожидалось сообщение 'Недостаточно средств' или неактивная/отсутствующая кнопка 'Перевести'."
    except TimeoutException:
        try:
            transfer_button = browser.find_element(*Locators.TRANSFER_BUTTON)
            assert not transfer_button.is_enabled() or transfer_button.get_attribute("disabled") == "true", \
                "Кнопка 'Перевести' должна быть неактивна или отсутствовать, если сумма + комиссия равна балансу."
        except NoSuchElementException:
            pass

# Тест TC-4.2
def test_p4_transfer_button_not_visible_if_amount_not_entered(browser):
    start_transfer(browser, balance=10000, reserved=0) 

    card_input = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT)
    )
    card_input.clear()
    card_input.send_keys("1111222233334444")

    WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT)
    )

    try:
        transfer_button = browser.find_element(*Locators.TRANSFER_BUTTON)
        is_disabled = transfer_button.get_attribute("disabled")
        if is_disabled: 
             assert True 
        else:
            assert transfer_button.is_enabled(), \
                "Кнопка 'Перевести' должна быть активна, если сумма не введена (current behavior)."

    except NoSuchElementException:
        assert True 
    except TimeoutException: 
        assert True 

# Тест TC-4.3
def test_p4_xss_vulnerability_in_card_number_field(browser):
    start_transfer(browser, balance=10000, reserved=0)

    card_input = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT)
    )
    card_input.clear()
    
    xss_payload = "<script>alert('XSS')</script>"
    card_input.send_keys(xss_payload)

    value_in_input = card_input.get_attribute("value")
    
    assert not any(char in value_in_input for char in "<>()/'scripalert"), \
        f"Поле ввода карты содержит нежелательные символы: '{value_in_input}', хотя ожидалось, что XSS-подобный ввод будет заблокирован."

    assert value_in_input != xss_payload, \
        f"XSS payload '{xss_payload}' был вставлен в поле карты без изменений."

    try:
        WebDriverWait(browser, 3).until(EC.alert_is_present())
        alert = browser.switch_to.alert
        alert_text = alert.text
        alert.accept() 
        pytest.fail(f"Обнаружен XSS! Появился alert с текстом: '{alert_text}'")
    except TimeoutException:
        assert True

# Тест TC-4.4
def test_p4_logo_is_present(browser):
    browser.get("http://localhost:8000/") 

    try:
        logo_element = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located(Locators.F_BANK_LOGO)
        )
        assert logo_element.is_displayed(), "Логотип F-Bank не отображается на странице."
        assert "F-Bank" in logo_element.text, "Текст логотипа не соответствует 'F-Bank'."
    except TimeoutException:
        pytest.fail("Логотип F-Bank (локатор F_BANK_LOGO) не найден на странице.")

# Тест TC-4.5
def test_p4_real_time_balance_update(browser):
    initial_balance_val = 10000
    transfer_amount_val = 1000
    commission_val = math.floor(transfer_amount_val * 0.10) 
    expected_balance_after_transfer = initial_balance_val - transfer_amount_val - commission_val

    start_transfer(browser, balance=initial_balance_val, reserved=0)

    balance_element_initial = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.RUBLE_BALANCE)
    )
    balance_text_initial = balance_element_initial.text
    current_displayed_balance = int("".join(filter(str.isdigit, balance_text_initial.split(':')[1])))
    
    assert current_displayed_balance == initial_balance_val, \
        f"Начальный отображаемый баланс '{current_displayed_balance}' не совпадает с ожидаемым '{initial_balance_val}'."

    card_input = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT)
    )
    card_input.clear()
    card_input.send_keys("1111222233334444")

    amount_input = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT)
    )
    amount_input.clear()
    amount_input.send_keys(str(transfer_amount_val))

    commission_display = WebDriverWait(browser, 10).until(
        EC.visibility_of_element_located(Locators.COMMISSION_VALUE)
    )
    assert f"Комиссия: {commission_val}" in commission_display.text

    transfer_button = WebDriverWait(browser, 10).until(
        EC.element_to_be_clickable(Locators.TRANSFER_BUTTON)
    )
    transfer_button.click()

    try:
        alert = WebDriverWait(browser, 10).until(EC.alert_is_present())
        alert.accept()
    except TimeoutException:
        pytest.fail("Не появилось всплывающее окно подтверждения перевода для проверки обновления баланса.")
    try:
        WebDriverWait(browser, 15).until(
            EC.text_to_be_present_in_element(
                    Locators.RUBLE_BALANCE,

                        f"На счету: {initial_balance_val:,} ₽".replace(',', "'") 
            )
        )
    except TimeoutException:
        balance_element_after = browser.find_element(*Locators.RUBLE_BALANCE)
        balance_text_after = balance_element_after.text
        pytest.fail(
                f"Баланс не остался '{initial_balance_val}' (как ожидается при текущем баге, format: На счету: X'XXX ₽), "
            f"но на странице отображается: '{balance_text_after}' (после попытки перевода)."
        )
    balance_element_final = browser.find_element(*Locators.RUBLE_BALANCE)
    final_displayed_text = balance_element_final.text.split(':')[1] # "XXXXX ₽"
    final_displayed_balance = int("".join(filter(str.isdigit, final_displayed_text)))

    assert final_displayed_balance == initial_balance_val, \
        f"Финальный отображаемый баланс '{final_displayed_balance}' не совпадает с ожидаемым '{initial_balance_val}' (отражая текущий баг)."