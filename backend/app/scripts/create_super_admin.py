import getpass

from pydantic import ValidationError

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest


def main() -> None:
    email = input("Email: ").strip().lower()
    username = input("Username: ").strip().lower()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")

    try:
        data = RegisterRequest(
            email=email, username=username, full_name=full_name, password=password
        )
    except ValidationError as exc:
        print("Invalid input:")
        for err in exc.errors():
            print(f"  - {err['loc'][0]}: {err['msg']}")
        return

    with SessionLocal() as db:
        repo = UserRepository(db)
        user = repo.get_by_email(data.email.lower())
        if user:
            user.is_super_admin = True
            print(f"Promoted existing user {user.email} to super admin.")
        else:
            repo.add(
                User(
                    email=data.email.lower(),
                    username=data.username.lower(),
                    full_name=data.full_name,
                    hashed_password=hash_password(data.password),
                    is_super_admin=True,
                )
            )
            print(f"Created super admin {data.email}.")
        db.commit()


if __name__ == "__main__":
    main()