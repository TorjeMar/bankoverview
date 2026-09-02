from app.features.accounts.schemas import (
    AccountBalanceResponse,
    AccountDetailsResponse,
    AccountsResponse,
    AccountTransactionResponse,
    AccountTransactionsResponse,
)
from app.integrations.enable_banking.schemas import (
    EnableBankingAccount,
    EnableBankingBalance,
    EnableBankingTransaction,
    EnableBankingTransactions,
    RetrievedEnableBankingSession,
)


def to_get_accounts_response(session: RetrievedEnableBankingSession) -> AccountsResponse:
    return AccountsResponse(
        accounts=session.accounts,
    )

def to_account_details_response(account: EnableBankingAccount) -> AccountDetailsResponse:
    return AccountDetailsResponse(
        account_id=account.account_id.model_dump(),
        all_account_ids=[
            identifier.model_dump() for identifier in (account.all_account_ids or [])
        ],
        account_servicer=(
            account.account_servicer.model_dump() if account.account_servicer else None
        ),
        name=account.name,
        details=account.details,
        usage=account.usage,
        cash_account_type=account.cash_account_type,
        product=account.product,
        currency=account.currency,
        credit_limit=account.credit_limit,
        postal_address=account.postal_address,
        uid=account.uid,
        identification_hash=account.identification_hash,
        identification_hashes=account.identification_hashes,
    )

def to_account_balance_response(
    account_id: str, balance: EnableBankingBalance
) -> AccountBalanceResponse:
    return AccountBalanceResponse(
        account_id=account_id,
        balances=balance.balances or [],
        balances_type=balance.balance_type,
        last_changed_date_time=balance.last_changed_date_time,
        refrenced_date=balance.refrenced_date,
        last_committed_transaction=balance.last_committed_transaction,
    )

def to_account_transactions_response(
    account_id: str, transactions: EnableBankingTransactions
) -> AccountTransactionsResponse:
    return AccountTransactionsResponse(
        account_id=account_id,
        transactions=transactions.transactions or [],
        continuation_key=transactions.continuation_key,
    )

def to_account_transaction_response(
    account_id: str, transaction: EnableBankingTransaction
) -> AccountTransactionResponse:
    return AccountTransactionResponse(
        account_id=account_id,
        entry_reference=transaction.entry_reference,
        merchant_category_code=transaction.merchant_category_code,
        transaction_amount=transaction.transaction_amount,
        creditor=transaction.creditor,
        creditor_account=transaction.creditor_account,
        creditor_agent=transaction.creditor_agent,
        debtor=transaction.debtor,
        debtor_account=transaction.debtor_account,
        debtor_agent=transaction.debtor_agent,
        bank_transaction_code=transaction.bank_transaction_code,
        credit_debit_indicator=transaction.credit_debit_indicator,
        status=transaction.status,
        booking_date=transaction.booking_date,
        value_date=transaction.value_date,
        transaction_date=transaction.transaction_date,
        balance_after_transaction=transaction.balance_after_transaction,
        refrence_number=transaction.refrence_number,
        refrence_number_schema=transaction.refrence_number_schema,
        remittance_information=transaction.remittance_information,
        debtor_account_additional_identification=transaction.debtor_account_additional_identification,
        creditor_account_additional_identification=transaction.creditor_account_additional_identification
    )