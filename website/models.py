from flask_login import UserMixin
class User(UserMixin):
    """
    A simplified User class compatible with Flask-Login.
    """
    def __init__(self, item_id, user_id=None, cv_path=None, uses=None, job_titles=None):
        self.item_id = item_id       # Primary identifier for the user
        self.user_id = user_id       # User ID from CMS
        self.cv_path = cv_path       # Path to the CV file
        self.uses = uses             # Number of uses
        self.job_titles = job_titles # Job titles for the user

    def get_id(self):
        """
        Override the get_id method to return a string ID.
        We'll use item_id as the unique identifier for Flask-Login.
        """
        return str(self.item_id)
# Optionally, implement other methods or properties as needed.
