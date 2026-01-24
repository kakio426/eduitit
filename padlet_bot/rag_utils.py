"""
패들릿 AI 챗봇 RAG 유틸리티

패들릿 내보내기 파일(PDF/CSV)에서 텍스트를 추출하고 ChromaDB에 임베딩하여 저장합니다.
기존 school_violence/rag_utils.py의 공통 함수를 재사용합니다.
"""

import os
import csv
import re
from typing import List, Optional

# ChromaDB 경로 설정
BASE_DIR = "/app/data" if os.environ.get('RAILWAY_ENVIRONMENT') else "."
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db_padlet")

# 폴더 생성
try:
    if not os.path.exists(CHROMA_PATH):
        os.makedirs(CHROMA_PATH, exist_ok=True)
except Exception as e:
    print(f"[WARNING] Failed to create ChromaDB directory: {e}")


# school_violence의 공통 함수 재사용
try:
    from school_violence.rag_utils import (
        extract_text_from_pdf,
        extract_text_from_txt,
        chunk_text,
    )
except ImportError:
    # 독립 실행 시 로컬 구현 사용
    def extract_text_from_pdf(file_path: str) -> str:
        """PDF 파일에서 텍스트 추출"""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            print(f"[ERROR] PDF 텍스트 추출 실패: {e}")
            return ""

    def extract_text_from_txt(file_path: str) -> str:
        """TXT 파일에서 텍스트 추출"""
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-16']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        return ""

    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """텍스트를 청크로 분할"""
        if not text:
            return []

        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 1 <= chunk_size:
                current_chunk += ("\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                if len(para) > chunk_size:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    current_chunk = ""
                    for sent in sentences:
                        if len(current_chunk) + len(sent) + 1 <= chunk_size:
                            current_chunk += (" " if current_chunk else "") + sent
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sent
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


def extract_text_from_csv(file_path: str) -> str:
    """
    CSV 파일에서 텍스트 추출 (패들릿 내보내기 형식)

    패들릿 CSV는 일반적으로 다음 열을 포함:
    - Subject/Title: 포스트 제목
    - Body/Content: 포스트 내용
    - Author: 작성자
    - Timestamp/Created: 작성 시간
    - Comments: 댓글
    """
    encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                # 먼저 구분자 감지 시도
                sample = f.read(4096)
                f.seek(0)

                # 구분자 자동 감지
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
                except csv.Error:
                    dialect = csv.excel

                reader = csv.DictReader(f, dialect=dialect)

                texts = []
                for row in reader:
                    post_parts = []

                    # 제목 필드 찾기 (다양한 이름 시도)
                    title_keys = ['Subject', 'Title', '제목', 'subject', 'title', 'Post Title']
                    for key in title_keys:
                        if key in row and row[key]:
                            post_parts.append(f"제목: {row[key].strip()}")
                            break

                    # 내용 필드 찾기
                    content_keys = ['Body', 'Content', '내용', 'body', 'content', 'Post Body', 'Text']
                    for key in content_keys:
                        if key in row and row[key]:
                            post_parts.append(f"내용: {row[key].strip()}")
                            break

                    # 작성자 필드 찾기
                    author_keys = ['Author', 'Creator', '작성자', 'author', 'creator', 'Name']
                    for key in author_keys:
                        if key in row and row[key]:
                            post_parts.append(f"작성자: {row[key].strip()}")
                            break

                    # 댓글 필드 찾기
                    comment_keys = ['Comments', 'Comment', '댓글', 'comments', 'Replies']
                    for key in comment_keys:
                        if key in row and row[key]:
                            post_parts.append(f"댓글: {row[key].strip()}")
                            break

                    # 필드가 없으면 모든 값 사용
                    if not post_parts:
                        post_parts = [f"{k}: {v}" for k, v in row.items() if v and v.strip()]

                    if post_parts:
                        texts.append("\n".join(post_parts))

                return "\n\n---\n\n".join(texts)

        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            print(f"[ERROR] CSV 파싱 오류 ({encoding}): {e}")
            continue

    return ""


def extract_text(file_path: str) -> str:
    """파일 확장자에 따라 적절한 텍스트 추출 방법 선택"""
    ext = file_path.lower().split('.')[-1]

    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext == 'csv':
        return extract_text_from_csv(file_path)
    elif ext in ['txt', 'md']:
        return extract_text_from_txt(file_path)
    else:
        print(f"[WARNING] 지원하지 않는 파일 형식: {ext}")
        return ""


class PadletRAG:
    """패들릿 AI 챗봇용 RAG 서비스"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.persist_directory = CHROMA_PATH
        self.client = None
        self.collection = None
        self.embedding_fn = None
        self._initialized = True

        self._init_chromadb()

    def _init_chromadb(self):
        """ChromaDB 초기화"""
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            self.collection = self.client.get_or_create_collection(
                name="padlet_posts",
                embedding_function=self.embedding_fn
            )
            print(f"[INFO] PadletRAG ChromaDB 초기화 완료: {self.persist_directory}")
        except ImportError:
            print("[ERROR] ChromaDB가 설치되지 않았습니다.")
            raise
        except Exception as e:
            print(f"[ERROR] ChromaDB 초기화 실패: {e}")
            raise

    def add_document(self, doc_id: int, file_path: str, title: str, file_type: str, user_id: int) -> int:
        """문서를 벡터DB에 추가"""
        if not self.collection:
            raise RuntimeError("ChromaDB가 초기화되지 않았습니다.")

        # 텍스트 추출
        text = extract_text(file_path)
        if not text:
            print(f"[WARNING] 텍스트 추출 실패: {file_path}")
            return 0

        # 청크 분할
        chunks = chunk_text(text)
        if not chunks:
            return 0

        # 기존 문서 청크 삭제 (업데이트용)
        self._delete_document_chunks(doc_id)

        # 청크 추가
        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"padlet_doc_{doc_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "doc_id": str(doc_id),
                "user_id": int(user_id),
                "title": title,
                "file_type": file_type,
                "chunk_index": i,
            })

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"[INFO] 패들릿 문서 추가 완료: {title} ({len(chunks)} 청크)")
        return len(chunks)

    def _delete_document_chunks(self, doc_id: int):
        """특정 문서의 모든 청크 삭제"""
        try:
            results = self.collection.get(
                where={"doc_id": str(doc_id)}
            )
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                print(f"[INFO] 기존 청크 삭제: {len(results['ids'])}개")
        except Exception as e:
            print(f"[WARNING] 청크 삭제 실패: {e}")

    def delete_document(self, doc_id: int):
        """문서 삭제"""
        self._delete_document_chunks(doc_id)

    def search(self, query: str, user_id: int, n_results: int = 5) -> List[dict]:
        """관련 문서 검색"""
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"user_id": int(user_id)}
            )

            search_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    search_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results.get('distances') else 0
                    })

            return search_results
        except Exception as e:
            print(f"[ERROR] 검색 실패: {e}")
            return []

    def get_context_for_query(self, query: str, user_id: int, n_results: int = 5) -> str:
        """쿼리에 대한 컨텍스트 문자열 생성"""
        results = self.search(query, user_id=user_id, n_results=n_results)

        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            title = result['metadata'].get('title', '알 수 없음')
            content = result['content']
            context_parts.append(f"[참고자료 {i}: {title}]\n{content}")

        return "\n\n---\n\n".join(context_parts)

    def get_document_count(self) -> int:
        """저장된 문서 청크 수 반환"""
        if not self.collection:
            return 0
        return self.collection.count()


# 싱글톤 인스턴스 가져오기
def get_padlet_rag_service() -> Optional[PadletRAG]:
    """패들릿 RAG 서비스 인스턴스 반환"""
    try:
        return PadletRAG()
    except Exception as e:
        print(f"[ERROR] 패들릿 RAG 서비스 초기화 실패: {e}")
        return None
