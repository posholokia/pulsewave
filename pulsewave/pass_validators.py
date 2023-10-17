from django.core.exceptions import ValidationError


class UppercaseLetterValidator:
    """
    Проверка, что в пароле есть минимум одна заглавная буква.
    """

    def validate(self, password, user=None):
        if not any(char.isupper() for char in password):
            raise ValidationError("Пароль должен содержать хотя бы одну букву в верхнем регистре.")

    def get_help_text(self):
        return "В пароле должна содержаться хотя бы одна строчная буква."


class LowercaseLetterValidator:
    """
    Проверка, что в пароле есть минимум одна строчная буква.
    """

    def validate(self, password, user=None):
        if not any(char.islower() for char in password):
            raise ValidationError("Пароль должен содержать хотя бы одну букву в нижнем регистре.")

    def get_help_text(self):
        return "В пароле должна содержаться хотя бы одна строчная буква."


class IncludeNumberValidator:
    """
    Проверка, что в пароле есть минимум одна цифра.
    """

    def validate(self, password, user=None):
        if not any(char.isdigit() for char in password):
            raise ValidationError("Пароль должен содержать хотя бы одну цифру.")

    def get_help_text(self):
        return "Пароль не может быть без цифр."


class SpecialCharacterValidator:
    """
    Проверка, что в пароле есть минимум один специальный символ.
    """

    def validate(self, password, user=None):
        special_characters = r"!@#$%^&*-_+[]{}|;:\,.<>?"
        if not any(char in special_characters for char in password):
            raise ValidationError("Пароль должен содержать хотя бы один специальный символ.")

    def get_help_text(self):
        return r"Пароль должен содержать минимум один специальный символ: !@#$%^&*-_+[]{}|;:\,.<>?"