"""
학교폭력 상담 RAG 유틸리티

PDF/HWP/TXT 파일에서 텍스트를 추출하고 ChromaDB에 임베딩하여 저장합니다.
"""

import os
import re
import uuid
from typing import List, Optional

# ChromaDB 경로 설정
BASE_DIR = "/app/data" if os.environ.get('RAILWAY_ENVIRONMENT') else "."
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db_school_violence")

# 폴더 생성
try:
    if not os.path.exists(CHROMA_PATH):
        os.makedirs(CHROMA_PATH, exist_ok=True)
except Exception as e:
    print(f"[WARNING] Failed to create ChromaDB directory: {e}")


def extract_text_from_pdf(file_path: str) -> str:
    """PDF 파일에서 텍스트 추출"""
    try:
        # PyPDF2 사용 시도
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except ImportError:
            pass

        # pdfplumber 사용 시도
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            return text
        except ImportError:
            pass

        return ""
    except Exception as e:
        print(f"[ERROR] PDF 텍스트 추출 실패: {e}")
        return ""


def extract_text_from_hwp(file_path: str) -> str:
    """HWP 파일에서 텍스트 추출 (olefile 사용)"""
    try:
        import olefile

        if not olefile.isOleFile(file_path):
            print(f"[WARNING] {file_path}는 OLE 형식이 아닙니다.")
            return ""

        ole = olefile.OleFileIO(file_path)

        # HWP 본문 스트림 읽기
        if ole.exists("BodyText/Section0"):
            data = ole.openstream("BodyText/Section0").read()
            # 간단한 텍스트 추출 (한글 인코딩)
            try:
                text = data.decode('utf-16', errors='ignore')
                # 제어 문자 제거
                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                return text
            except Exception:
                pass

        ole.close()
        return ""
    except ImportError:
        print("[WARNING] olefile이 설치되지 않았습니다. HWP 파일을 처리할 수 없습니다.")
        return ""
    except Exception as e:
        print(f"[ERROR] HWP 텍스트 추출 실패: {e}")
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


def extract_text(file_path: str) -> str:
    """파일 확장자에 따라 적절한 텍스트 추출 방법 선택"""
    ext = file_path.lower().split('.')[-1]

    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext == 'hwp':
        return extract_text_from_hwp(file_path)
    elif ext in ['txt', 'md']:
        return extract_text_from_txt(file_path)
    else:
        print(f"[WARNING] 지원하지 않는 파일 형식: {ext}")
        return ""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """텍스트를 청크로 분할"""
    if not text:
        return []

    # 문단 기준으로 먼저 분할
    paragraphs = re.split(r'\n\s*\n', text)

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 현재 청크에 추가해도 크기 제한 내라면 추가
        if len(current_chunk) + len(para) + 1 <= chunk_size:
            current_chunk += ("\n" if current_chunk else "") + para
        else:
            # 현재 청크 저장
            if current_chunk:
                chunks.append(current_chunk)

            # 문단이 청크 크기보다 크면 문장 단위로 분할
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

    # 마지막 청크 저장
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


class SchoolViolenceRAG:
    """학교폭력 상담용 RAG 서비스"""

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
                name="school_violence_guidelines",
                embedding_function=self.embedding_fn
            )
            print(f"[INFO] ChromaDB 초기화 완료: {self.persist_directory}")
        except ImportError:
            print("[ERROR] ChromaDB가 설치되지 않았습니다.")
            raise
        except Exception as e:
            print(f"[ERROR] ChromaDB 초기화 실패: {e}")
            raise

    def add_document(self, doc_id: int, file_path: str, title: str, category: str) -> int:
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
            chunk_id = f"doc_{doc_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "doc_id": str(doc_id),
                "title": title,
                "category": category,
                "chunk_index": i,
            })

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(f"[INFO] 문서 추가 완료: {title} ({len(chunks)} 청크)")
        return len(chunks)

    def _delete_document_chunks(self, doc_id: int):
        """특정 문서의 모든 청크 삭제"""
        try:
            # 해당 문서의 청크 ID 조회
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

    def search(self, query: str, n_results: int = 5, category: Optional[str] = None) -> List[dict]:
        """관련 문서 검색"""
        if not self.collection:
            return []

        try:
            where_filter = {"category": category} if category else None

            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
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

    def get_context_for_query(self, query: str, n_results: int = 3) -> str:
        """쿼리에 대한 컨텍스트 문자열 생성"""
        results = self.search(query, n_results=n_results)

        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            title = result['metadata'].get('title', '알 수 없음')
            content = result['content']
            context_parts.append(f"[참고자료 {i}: {title}]\n{content}")

        return "\n\n---\n\n".join(context_parts)


# 싱글톤 인스턴스 가져오기
def get_rag_service() -> Optional[SchoolViolenceRAG]:
    """RAG 서비스 인스턴스 반환"""
    try:
        return SchoolViolenceRAG()
    except Exception as e:
        print(f"[ERROR] RAG 서비스 초기화 실패: {e}")
        return None
