import logging

from pliris.agents.ba_agent import BAAgent
from pliris.database.repositories.conversations import ConversationRepository
from pliris.guardrails.evidence_checker import EvidenceChecker
from pliris.guardrails.response_guardrail import ResponseGuardrail
from pliris.retrieval.hybrid_search import HybridSearch
from pliris.retrieval.query_rewriter import QueryRewriter
from pliris.retrieval.reranker import Reranker

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates the entire query processing pipeline."""

    def __init__(self):
        self.ba_agent = BAAgent()
        self.search = HybridSearch()
        self.query_rewriter = QueryRewriter()
        self.reranker = Reranker()
        self.evidence_checker = EvidenceChecker()
        self.response_guardrail = ResponseGuardrail()
        self.conversation_repo = ConversationRepository()

    async def process_query(
        self, message: str, conversation_id: str | None = None, user_id: str = "system"
    ) -> dict:
        """
        Process a user query through the complete pipeline.

        Pipeline:
        1. Get or create conversation
        2. Retrieve conversation history
        3. Rewrite query for better retrieval
        4. Hybrid search (semantic + lexical)
        5. Rerank results
        6. Generate response with BA agent
        7. Check evidence
        8. Apply response guardrails
        9. Store message and return response
        """
        try:
            # Get or create conversation
            if not conversation_id:
                conversation_id = await self.conversation_repo.create(user_id)

            # Get conversation history
            history = await self.conversation_repo.get_messages(conversation_id)

            # Rewrite query
            rewritten_query = await self.query_rewriter.rewrite(message, history)
            logger.info(f"Rewritten query: {rewritten_query}")

            # Hybrid search
            search_results = await self.search.search(query=rewritten_query, top_k=20)

            # Rerank results
            reranked = await self.reranker.rerank(query=message, results=search_results, top_k=5)

            # Generate response
            response_data = await self.ba_agent.process_query(
                query=message, context=reranked, conversation_history=history
            )

            # Check evidence
            evidence_score = await self.evidence_checker.check(
                response=response_data["response"], context=reranked
            )

            # Apply response guardrails
            guarded_response = await self.response_guardrail.guard(
                response=response_data["response"]
            )

            # Store user message
            await self.conversation_repo.add_message(
                conversation_id=conversation_id, role="user", content=message
            )

            # Store assistant message
            await self.conversation_repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=guarded_response,
                metadata={
                    "citations": response_data["citations"],
                    "evidence_score": evidence_score,
                },
            )

            return {
                "response": guarded_response,
                "citations": response_data["citations"],
                "confidence": evidence_score,
                "conversation_id": conversation_id,
                "rewritten_query": rewritten_query,
            }

        except Exception as e:
            logger.error(f"Error in orchestrator: {e}", exc_info=True)
            raise
