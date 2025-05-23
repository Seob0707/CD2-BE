import os
import time
import logging
import asyncio
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

async def _remove_file_if_exists_async(file_path: Path) -> bool:
    try:
        if await asyncio.to_thread(file_path.is_file):
            await asyncio.to_thread(file_path.unlink)
            logger.info(f"오래된 임시 파일 삭제 성공: {file_path}")
            return True
        elif not await asyncio.to_thread(file_path.exists):
             logger.debug(f"삭제 시도 중 파일이 이미 존재하지 않음: {file_path}")
        else:
            logger.debug(f"경로가 파일이 아니므로 삭제하지 않음: {file_path}")
        return False
    except Exception as e:
        logger.error(f"파일 삭제 중 오류 발생 {file_path}: {e}", exc_info=True)
        return False

async def _remove_directory_if_empty_async(dir_path: Path) -> bool:
    try:
        if await asyncio.to_thread(dir_path.is_dir):
            if not any(await asyncio.to_thread(list, dir_path.iterdir())):
                await asyncio.to_thread(dir_path.rmdir)
                logger.info(f"비어있는 임시 세션 디렉터리 삭제 성공: {dir_path}")
                return True
            else:
                logger.debug(f"디렉터리가 비어있지 않아 삭제하지 않음: {dir_path}")
        else:
            logger.debug(f"삭제 시도 중 경로가 디렉터리가 아님: {dir_path}")
        return False
    except FileNotFoundError:
        logger.warning(f"디렉터리 처리 중 찾을 수 없음 (이미 삭제된 것일 수 있음): {dir_path}")
        return False
    except Exception as e:
        logger.error(f"디렉터리 삭제 중 오류 발생 {dir_path}: {e}", exc_info=True)
        return False

async def cleanup_old_temporary_files():
    upload_dir_str = settings.UPLOAD_DIR
    ttl_hours = settings.TEMP_FILE_TTL_HOURS
    file_ttl_seconds = ttl_hours * 60 * 60

    logger.info(
        f"'{upload_dir_str}' 디렉터리에서 {ttl_hours}시간({file_ttl_seconds}초) 이상된 "
        f"임시 파일 정리를 시작합니다."
    )
    now = time.time()
    upload_path = Path(upload_dir_str)

    if not upload_path.exists() or not upload_path.is_dir():
        logger.warning(
            f"업로드 디렉터리 '{upload_dir_str}'가 존재하지 않거나 디렉터리가 아닙니다. "
            f"정리를 건너<0xEB><0x9B><0x84>니다."
        )
        return

    total_files_cleaned = 0
    total_dirs_cleaned = 0

    try:
        session_directories = await asyncio.to_thread(
            lambda p: [x for x in p.iterdir() if x.is_dir()],
            upload_path
        )

        for session_dir_path in session_directories:
            logger.debug(f"세션 디렉터리 처리 중: {session_dir_path}")
            try:
                items_in_session_dir = await asyncio.to_thread(list, session_dir_path.iterdir())
                for item_path in items_in_session_dir:
                    if await asyncio.to_thread(item_path.is_file):
                        try:
                            file_mod_time = await asyncio.to_thread(lambda p: p.stat().st_mtime, item_path)
                            if (now - file_mod_time) > file_ttl_seconds:
                                if await _remove_file_if_exists_async(item_path):
                                    total_files_cleaned += 1
                        except FileNotFoundError:
                            logger.warning(f"정리 중 파일({item_path})을 찾을 수 없어 건너<0xEB><0x9B><0x84>니다. (이미 삭제된 것일 수 있음)")
                        except Exception as e:
                            logger.error(f"임시 파일({item_path}) 처리 중 오류: {e}", exc_info=True)

                if await _remove_directory_if_empty_async(session_dir_path):
                    total_dirs_cleaned +=1
            except Exception as e:
                 logger.error(f"세션 디렉터리({session_dir_path}) 처리 중 오류: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"임시 파일 정리 작업 중 최상위 수준 오류 발생: {e}", exc_info=True)

    logger.info(
        f"임시 파일 정리 작업 완료. 총 삭제된 파일 수: {total_files_cleaned}, "
        f"총 삭제된 빈 세션 디렉터리 수: {total_dirs_cleaned}"
    )