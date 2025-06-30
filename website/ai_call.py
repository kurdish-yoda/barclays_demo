from flask import session, current_app
from openai import AzureOpenAI # openai v1.x+ is synchronous by default
from .secrets import get_secret # Your existing secrets function
import http.client # For HTTPException
import tiktoken

# For Azure AI Search (Synchronous version)
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient # Synchronous version
from azure.search.documents.models import VectorizedQuery # Model class is often shared

class AzureAIAgent:
    def __init__(self, deployment_name="o4-mini"):
        # --- OpenAI Client Initialization ---
        self.chat_api_key = get_secret('KEY1-AI-US')
        self.chat_azure_endpoint = get_secret('AI-ENDPOINT-US')
        self.api_version = "2025-04-01-preview" # Ensure this is a valid, current string version

        self.client = AzureOpenAI(
            api_key=self.chat_api_key,
            api_version=self.api_version,
            azure_endpoint=self.chat_azure_endpoint
        )


        self.deployment_name = deployment_name
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.embedding_deployment_name = "text-embedding-3-large"

        # --- Azure AI Search Client Initialization (Synchronous) ---
        self.search_endpoint = "https://stewardsearch.search.windows.net"
        self.search_query_key = get_secret('STEWARD-SEARCH-API-KEY')
        self.search_index_name ="txt-rag-index-barclay"

        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.search_index_name,
            credential=AzureKeyCredential(self.search_query_key)
        )

    def count_tokens(self, messages):
        num_tokens = 0
        for message in messages:
            content_to_encode = message.get("content", "")
            if not isinstance(content_to_encode, str):
                content_to_encode = ""
            num_tokens += len(self.encoding.encode(content_to_encode))
            num_tokens += 3
        return num_tokens

    def _get_embedding(self, text_to_embed):
        if not self.client:
            current_app.logger.warning("AzureOpenAI client not available. Skipping embedding.")
            return None
        if not self.embedding_deployment_name:
            current_app.logger.error("Embedding deployment name not configured. Skipping embedding.")
            return None
        try:
            # OpenAI v1.x client.embeddings.create is synchronous
            response = self.client.embeddings.create(
                model=self.embedding_deployment_name,
                input=[text_to_embed]
            )
            return response.data[0].embedding
        except Exception as e:
            current_app.logger.error(f"Error generating embedding for text '{text_to_embed[:50]}...': {e}", exc_info=True)
            return None

    def _search_relevant_chunks(self, query_embedding, top_k=5): # Changed top_k to 5 as per your last code
        if not self.search_client:
            current_app.logger.warning("Search client not available (sync). Skipping search.")
            return []
        if not query_embedding:
            current_app.logger.warning("No query embedding provided (sync). Skipping search.")
            return []

        try:
            vector_query = VectorizedQuery(vector=query_embedding, k_nearest_neighbors=top_k, fields="embedding")

            # Synchronous call
            results = self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                select=["id", "text_chunk", "source_txt"]
            )

            retrieved_chunks = []
            for result in results:
                retrieved_chunks.append({
                    "id": result.get("id"),
                    "score": result.get("@search.score"),
                    "text": result.get("text_chunk"),
                    "source": result.get("source_txt"),
                })
            return retrieved_chunks
        except Exception as e:
            current_app.logger.error(f"Error searching for relevant chunks (sync): {e}", exc_info=True)
            return []

    def load_system_prompt_from_file(self):
        try:
            prompt_text = session.get('prompt')
            if prompt_text:
                prompt_text = prompt_text.strip()
                if prompt_text:
                    session['conversation_log'] = [{"role": "system", "content": prompt_text}]
                    session.modified = True
                else:
                    raise ValueError("Empty prompt after stripping. Using default prompt.")
            else:
                raise ValueError("Prompt not found in session. Using default prompt.")
        except Exception as e:
            current_app.logger.error(f"Error loading system prompt (sync): {e}")
            session['conversation_log'] = [{"role": "system", "content": "You are a friendly AI interviewer."}]
            session.modified = True

    def send_to_azure_agent(self):
        if not self.client:
            current_app.logger.error("AzureOpenAI client not initialized. Cannot send message.")
            return "I'm sorry, there's a configuration issue with the AI service."

        if 'conversation_log' not in session or not session['conversation_log']:
            self.load_system_prompt_from_file()

        # --- Start of RAG Logic ---
        rag_input_text = ""
        retrieved_chunks_for_logging = [] # This will now hold chunks to be used for context

        if session.get('conversation_log') and isinstance(session['conversation_log'], list) and len(session['conversation_log']) > 0:
            log_to_modify_for_rag = [dict(msg) for msg in session['conversation_log']]
            current_app.logger.info(f"RAG Prep: Original log length for RAG processing: {len(log_to_modify_for_rag)}")

            idx_to_remove_system = -1
            for i, msg in enumerate(log_to_modify_for_rag):
                if msg.get("role") == "system":
                    idx_to_remove_system = i
                    break
            if idx_to_remove_system != -1:
                log_to_modify_for_rag.pop(idx_to_remove_system)
                current_app.logger.info(f"RAG Prep: Removed 'system' message. New log length for RAG: {len(log_to_modify_for_rag)}")
            else:
                current_app.logger.info("RAG Prep: No 'system' message found to remove for RAG.")

            assistant_messages_removed_count = 0
            while log_to_modify_for_rag and log_to_modify_for_rag[0].get("role") == "assistant":
                log_to_modify_for_rag.pop(0)
                assistant_messages_removed_count += 1

            if assistant_messages_removed_count > 0:
                current_app.logger.info(f"RAG Prep: Removed {assistant_messages_removed_count} leading 'assistant' message(s). New log length for RAG: {len(log_to_modify_for_rag)}")
            else:
                current_app.logger.info("RAG Prep: No leading 'assistant' messages found to remove after 'system' message removal attempt.")

            idx_to_remove_user = -1
            for i, msg in enumerate(log_to_modify_for_rag):
                if msg.get("role") == "user":
                    idx_to_remove_user = i
                    break
            if idx_to_remove_user != -1:
                log_to_modify_for_rag.pop(idx_to_remove_user)
                current_app.logger.info(f"RAG Prep: Removed first 'user' message (at index {idx_to_remove_user} of modified list). New log length for RAG: {len(log_to_modify_for_rag)}")
            else:
                current_app.logger.info("RAG Prep: No 'user' message found to remove after 'system' and 'assistant' removal attempts.")

            if log_to_modify_for_rag:
                for message in log_to_modify_for_rag:
                    content = message.get("content")
                    if isinstance(content, str):
                        rag_input_text += content + "\n"
                rag_input_text = rag_input_text.strip()
                if rag_input_text:
                     # Using your latest log format for constructed RAG input text
                     current_app.logger.debug(f"RAG Prep: Constructed RAG input text from modified log (first 200 chars): '{rag_input_text}...'")
                else:
                    current_app.logger.info("RAG Prep: Modified log for RAG resulted in empty content string after concatenation.")
            else:
                current_app.logger.info("RAG Prep: Modified conversation log for RAG is empty. No RAG input text will be generated.")
        else:
            current_app.logger.info("RAG Prep: Session conversation_log is empty, not found, or not a list initially. Skipping RAG preparation.")

        current_app.logger.debug(f"RAG Execution Check: rag_input_text='{rag_input_text[:50] if rag_input_text else ''}...' (Length: {len(rag_input_text) if rag_input_text else 0}, Type: {type(rag_input_text)})")

        if rag_input_text:
            current_app.logger.info("RAG Execution: Performing RAG with query from modified log.")
            query_embedding = self._get_embedding(rag_input_text)
            if query_embedding:
                # `retrieved_chunks_for_logging` will now be used for actual context
                retrieved_chunks_for_logging = self._search_relevant_chunks(query_embedding, top_k=5) # Using top_k=5
                if retrieved_chunks_for_logging:
                    current_app.logger.info(f"RAG Execution: Retrieved {len(retrieved_chunks_for_logging)} relevant chunks (sync):")
                    for i, chunk_info in enumerate(retrieved_chunks_for_logging):
                        score_val = chunk_info.get('score')
                        score_str = f"{score_val:.4f}" if isinstance(score_val, (float, int)) else str(score_val if score_val is not None else "N/A")
                        current_app.logger.info(
                            f"  Chunk {i+1} (ID: {chunk_info.get('id')}, Score: {score_str}, Source: {chunk_info.get('source', 'N/A')}): "
                            f"'{chunk_info.get('text', '')[:150]}...'"
                        )
                else:
                    current_app.logger.info("RAG Execution: No relevant chunks retrieved from Azure AI Search (sync) for the modified query.")
            else:
                current_app.logger.info("RAG Execution: Could not generate embedding for the combined query from modified log (sync). Skipping retrieval.")
        else:
            current_app.logger.info("RAG Execution: No RAG input text available (log was empty after modifications or originally unsuitable). Skipping RAG.")
        # --- End of RAG Logic ---

        # --- Prepare messages for LLM, potentially with RAG context ---
        messages_for_llm = [dict(msg) for msg in session['conversation_log']] # Start with a copy of the original log

        if retrieved_chunks_for_logging: # If RAG provided chunks
            context_header = "System note: The following information has been retrieved from relevant Sage product documents, and you can use as context where appropriate:"
            context_parts = [context_header]
            for i, chunk in enumerate(retrieved_chunks_for_logging):
                text_chunk = chunk.get('text', '')
                context_parts.append(f"\n--- Retrieved Document Snippet {i+1} ---\n{text_chunk}")

            context_message_content = "\n".join(context_parts)
            context_system_message = {"role": "system", "content": context_message_content}

            # Insert the context message.
            # A good place is after an initial system prompt, if one exists and is first.
            if messages_for_llm and messages_for_llm[0].get("role") == "system":
                messages_for_llm.insert(1, context_system_message)
                current_app.logger.info("RAG Context: Injected retrieved context as a new system message after the initial system prompt.")
            else:
                # If no initial system prompt, or log is empty, insert at the beginning.
                messages_for_llm.insert(0, context_system_message)
                current_app.logger.info("RAG Context: Injected retrieved context as a new system message at the beginning.")
        else:
            current_app.logger.info("RAG Context: No chunks to inject, or RAG was skipped. Using original conversation log structure for LLM.")
        # --- End of RAG context injection ---


        if session.get('prompt') == "<-- IS NOT CV -->":
            return "The provided file was not a CV/resume. Please upload a valid CV/resume."

        try:
            # Log the messages that will actually be sent to the LLM, including any injected context
            current_app.logger.info(f"LLM Call: Sending {len(messages_for_llm)} messages to the LLM. Preview: {messages_for_llm}...")

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages_for_llm, # Use the (potentially augmented) list
                max_completion_tokens=12000,
                temperature=1
            )

            ai_response = response.choices[0].message.content.strip()

            # Append only the AI's direct response to the persistent conversation_log
            if 'conversation_log' not in session or not isinstance(session['conversation_log'], list):
                session['conversation_log'] = []
            session['conversation_log'].append({"role": "assistant", "content": ai_response})
            session.modified = True

            # Metrics (synchronous calculation)
            # input_tokens = self.count_tokens(messages_for_llm) # Count tokens from what was actually sent
            # output_tokens = len(self.encoding.encode(ai_response))
            # output_character_count = len(ai_response)
            # session['user_metrics']['inputTokensCoach'] += input_tokens
            # session['user_metrics']['outputTokensCoach'] += output_tokens
            # session['user_metrics']['outputCharacterCoach'] += output_character_count
            # session['user_metrics']['coachQuestionsAsked'] += 1

            return ai_response

        except Exception as e:
            error_str = str(e)
            current_app.logger.error(f"Error in send_to_azure_agent during LLM call (sync): {e}", exc_info=True)

            if "content_filter" in error_str:
                current_app.logger.warning(f"Content filtered (sync): {e}")
                return "I'm sorry, but your message violates our community standards. Please try again."
            elif isinstance(e, http.client.HTTPException) or "network error" in error_str.lower():
                current_app.logger.error(f"HTTP error in send_to_azure_agent (sync): {e}")
                return "I'm sorry, there was a network error. Please try again later."
            else:
                return "I'm sorry, an unexpected error occurred. Please try again later."
