import pytest
import math
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

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


# --- Фикстура для инициализации и закрытия браузера ---
@pytest.fixture
def browser():
    print("\nНастройка драйвера для Edge")
    service = EdgeService(executable_path=EdgeChromiumDriverManager().install())
    options = webdriver.EdgeOptions()
    driver = webdriver.Edge(service=service, options=options)
    
    driver.implicitly_wait(5)
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
def test_p1_max_possible_transfer_shows_alert(browser):
    """Проверяет, что при успешном переводе появляется alert-уведомление."""
    start_transfer(browser, balance=9999, reserved=0)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("9090")
    
    transfer_button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON))
    transfer_button.click()
    
    alert = WebDriverWait(browser, 10).until(EC.alert_is_present())
    assert "принят банком" in alert.text
    alert.accept()

# Тест TC-4.2
def test_p1_transfer_button_disappears_on_clear(browser):
    """Проверяет, что кнопка 'Перевести' видна при дефолтном значении, но исчезает при очистке поля."""
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")

    WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_BUTTON))

    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    
    assert WebDriverWait(browser, 5).until(EC.invisibility_of_element_located(Locators.TRANSFER_BUTTON))

# Тест TC-4.3
def test_p1_card_input_accepts_only_digits(browser):
    """Проверяет, что поле ввода карты не принимает буквы."""
    start_transfer(browser)
    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("abcd1234efgh5678")
    
    assert card_input.get_attribute("value") == "12345678"

# Тест TC-4.4
def test_p1_logo_is_present(browser):
    """Проверяет наличие логотипа."""
    browser.get("http://localhost:8000")
    logo = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.F_BANK_LOGO))
    assert logo.is_displayed() and "F-Bank" in logo.text

# Тест TC-4.5
def test_p1_balance_does_not_update_after_transfer(browser):
    """Проверяет дефект: баланс на странице не обновляется после перевода."""
    start_transfer(browser, balance=10000, reserved=0)
    initial_balance_element = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.RUBLE_BALANCE))
    initial_balance_text = initial_balance_element.text

    card_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.CARD_NUMBER_INPUT))
    card_input.clear()
    card_input.send_keys("1111222233334444")
    
    amount_input = WebDriverWait(browser, 10).until(EC.visibility_of_element_located(Locators.TRANSFER_AMOUNT_INPUT))
    amount_input.clear()
    amount_input.send_keys("1000")
    
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(Locators.TRANSFER_BUTTON)).click()
    WebDriverWait(browser, 10).until(EC.alert_is_present()).accept()
    
    time.sleep(1) 

    final_balance_text = browser.find_element(*Locators.RUBLE_BALANCE).text
    assert final_balance_text == initial_balance_text
