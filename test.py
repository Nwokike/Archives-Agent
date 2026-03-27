import os
import json
import shutil
import tempfile
import asyncio

from huggingface_hub import hf_hub_download

TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")

async def image_downloader(repo_id: str, file_name: str) -> str:
    try:
        await asyncio.sleep(1.0)
        path = await asyncio.to_thread(
            hf_hub_download, repo_id=repo_id, filename=f"images/{file_name}", repo_type="dataset"
        )
        safe_path = os.path.join(tempfile.gettempdir(), os.path.basename(path))
        shutil.copy2(path, safe_path)
        return safe_path
    except Exception as e:
        # HARD ABORT: Prevent pipeline from proceeding with no image
        raise RuntimeError(f"FATAL: Image download failed. Aborting pipeline. Details: {str(e)}")

async def process_hf_row(index: int) -> dict:
    """Extracts the RAW, unadulterated metadata from Hugging Face."""
    try:
        await asyncio.sleep(1.5)
        metadata_path = await asyncio.to_thread(
            hf_hub_download, repo_id=TARGET_DATASET, filename="data.jsonl", repo_type="dataset"
        )
        record = None
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i == index:
                    record = json.loads(line)
                    break
        
        if not record: 
            raise ValueError(f"FATAL: Record not found at index {index}. Aborting pipeline.")
        
        # WE PASS THE FULL, UNTRUNCATED METADATA DICTIONARY
        metadata = record.get("metadata", {})
        
        images = record.get("images", [])
        file_name = images[0].get("file_name") if images else ""
        
        image_local_path = ""
        if file_name:
            image_local_path = await image_downloader(TARGET_DATASET, file_name)
        else:
            raise ValueError("FATAL: No image found in the Hugging Face record. Vision agent cannot proceed.")
            
        return {
            "raw_metadata": record, 
            "image_path": image_local_path
        }
    except Exception as e:
        # Re-raise to ensure the agent orchestrator catches the hard stop
        raise RuntimeError(f"PIPELINE ABORTED: {str(e)}")

if __name__ == "__main__":
    async def main():
        print("🚀 Starting HF Metadata Fetcher Test...")
        try:
            # We test with the first row (index 0)
            test_index = 0
            result = await process_hf_row(test_index)
            
            print(f"\n✅ Successfully fetched record at index {test_index}")
            print(f"📁 Image saved to: {result['image_path']}")
            print("\n📄 Metadata Sample")
            raw = result["raw_metadata"]
            for key in list(raw.keys()):
                print(f"  - {key}: {str(raw[key])}")
                
            if os.path.exists(result["image_path"]):
                print(f"\n✨ IMAGE VERIFIED: {os.path.getsize(result['image_path'])} bytes")
            else:
                print("\n❌ ERROR: Image path returned but file not found on disk.")
                
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")

    asyncio.run(main())
