from pydantic import BaseModel, Field


class RenameAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)


class RenameAccountResponse(BaseModel):
    account_id: str
    display_name: str | None = None


class ReorderAccountsRequest(BaseModel):
    account_ids: list[str]
