import os
import boto3
import time
import json
from botocore.exceptions import ClientError, NoCredentialsError
import ProcessLogger
from datetime import datetime

class TextractPdfTextExtractor:
    logger = ProcessLogger.getLogger('Textract')

    def __init__(self, indir, outdir, pages, language):
        self.indir = indir
        self.outdir = outdir
        self.pages = pages
        self.language = language
        
        # Initialize AWS Textract client with environment variables
        self.textract_client = self._initialize_textract_client()
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)
        
        # Language mapping for Textract
        self.language_mapping = {
            'english': 'en',
            'french': 'fr', 
            'spanish': 'es',
            'portuguese': 'pt',
            'arabic': 'ar',
            'portuguesestandard': 'pt'
        }

    def _initialize_textract_client(self):
        """
        Initialize Textract client using environment variables
        """
        try:
            # Check if we have AWS credentials in environment
            aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            
            if aws_access_key and aws_secret_key:
                self.logger.info(f'Using AWS credentials from environment variables')
                return boto3.client(
                    'textract',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                # Fall back to default credential chain (IAM roles, etc.)
                self.logger.info(f'Using AWS default credential chain')
                return boto3.client('textract', region_name=aws_region)
                
        except Exception as e:
            self.logger.error(f'Failed to initialize Textract client: {e}')
            raise


    def processDocumentWithS3Url(self, s3_url):
        """
        Process entire PDF document using S3 URL directly
        """
        try:
            # Extract bucket and key from S3 URL
            bucket = self._extract_bucket_from_url(s3_url)
            key = self._extract_key_from_url(s3_url)
            
            self.logger.info(f'Processing document: {s3_url}')
            
            # Start comprehensive document analysis
            response = self.textract_client.start_document_analysis(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                },
                FeatureTypes=['TABLES', 'FORMS']
            )
            
            job_id = response['JobId']
            self.logger.info(f'Textract job started: {job_id}')
            
            # Wait for job completion
            blocks = self._wait_for_completion(job_id)
            
            # Process extracted data with comprehensive features
            processed_result = self._process_extracted_data(blocks)
            
            # Write output files
            self._write_output_files(processed_result)
            
            return processed_result
                
        except ClientError as e:
            self.logger.error(f'AWS Textract error: {e}')
            raise
        except Exception as e:
            self.logger.error(f'Unexpected error: {e}')
            raise

    def _extract_bucket_from_url(self, url):
        """
        Extract bucket name from S3 URL
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        if parsed.scheme == 's3':
            return parsed.hostname
        
        if '.s3.' in parsed.hostname and '.amazonaws.com' in parsed.hostname:
            hostname_parts = parsed.hostname.split('.')
            return hostname_parts[0]
        
        if parsed.hostname == 's3.amazonaws.com':
            return parsed.path.split('/')[1]
        
        raise ValueError(f"Invalid S3 URL format: {url}")

    def _extract_key_from_url(self, url):
        """
        Extract key from S3 URL
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        if parsed.scheme == 's3':
            return parsed.path[1:]  # Remove leading slash
        
        if '.s3.' in parsed.hostname and '.amazonaws.com' in parsed.hostname:
            return parsed.path[1:]  # Remove leading slash
        
        if parsed.hostname == 's3.amazonaws.com':
            return '/'.join(parsed.path.split('/')[2:])  # Skip bucket name
        
        raise ValueError(f"Invalid S3 URL format: {url}")

    def _wait_for_completion(self, job_id, max_wait_time=600):
        """
        Wait for Textract job to complete and return blocks
        Handle pagination to get all blocks
        """
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait_time:
                raise Exception(f'Textract job timed out after {max_wait_time} seconds')
                
            response = self.textract_client.get_document_analysis(JobId=job_id)
            status = response['JobStatus']
            
            if status == 'SUCCEEDED':
                # Collect all blocks, handling pagination
                all_blocks = response.get('Blocks', [])
                next_token = response.get('NextToken')
                
                # Handle pagination
                while next_token:
                    next_response = self.textract_client.get_document_analysis(
                        JobId=job_id,
                        NextToken=next_token
                    )
                    next_blocks = next_response.get('Blocks', [])
                    all_blocks.extend(next_blocks)
                    next_token = next_response.get('NextToken')
                
                self.logger.info(f'Textract analysis completed: {len(all_blocks)} blocks collected')
                return all_blocks
            elif status == 'FAILED':
                raise Exception(f'Textract job failed: {response.get("StatusMessage", "Unknown error")}')
            elif status == 'IN_PROGRESS':
                time.sleep(5)
            else:
                raise Exception(f'Unexpected job status: {status}')

    def _process_extracted_data(self, blocks):
        """
        Comprehensive data processing similar to JavaScript implementation
        """
        start_time = time.time()

        # Separate different block types
        text_blocks = [block for block in blocks if block['BlockType'] == 'LINE']
        table_blocks = [block for block in blocks if block['BlockType'] == 'TABLE']
        form_blocks = [block for block in blocks if block['BlockType'] == 'KEY_VALUE_SET']
        page_blocks = [block for block in blocks if block['BlockType'] == 'PAGE']

        # Process text with layout preservation
        processed_text = self._process_text_with_layout(text_blocks)

        # Process tables with enhanced structure
        processed_tables = self._process_tables_enhanced(table_blocks, blocks)

        # Process forms and key-value pairs
        processed_forms = self._process_forms_enhanced(form_blocks, blocks)

        # Calculate confidence scores
        confidence = self._calculate_confidence(blocks, threshold=80)

        # Generate statistics
        statistics = {
            'textBlocks': len(text_blocks),
            'tables': len(table_blocks),
            'forms': len(form_blocks),
            'pages': len(page_blocks),
            'totalBlocks': len(blocks),
            'averageConfidence': confidence['average'],
        }

        processing_time = time.time() - start_time

        # Handle single vs multi-page documents
        if len(page_blocks) > 1:
            # Multi-page document - separate by pages
            pages_data = []
            for page_num, page_block in enumerate(page_blocks, 1):
                # Get blocks for this specific page
                page_blocks_data = [block for block in blocks if block.get('Page') == page_num]
                
                # Filter text blocks for this page
                page_text_blocks = [block for block in page_blocks_data if block['BlockType'] == 'LINE']
                
                # Process text for this page
                page_text = self._process_text_with_layout(page_text_blocks)
                
                # Calculate confidence for this page
                page_confidence = self._calculate_confidence(page_blocks_data, threshold=80)
                
                # Always add page, even if empty (to maintain page numbering)
                pages_data.append({
                    'page': page_num,
                    'text': page_text,
                    'statistics': {
                        'textBlocks': len(page_text_blocks),
                        'confidence': page_confidence['average'],
                    }
                })
            
            return {
                'pages': pages_data,
                'totalPages': len(page_blocks),
                'overallStatistics': statistics,
                'structuredData': {
                    'tables': processed_tables,
                    'forms': processed_forms,
                },
                'layout': self._generate_layout_map(blocks),
                'confidence': confidence,
                'processingTime': processing_time,
            }
        else:
            # Single page document
            return {
                'text': processed_text,
                'structuredData': {
                    'tables': processed_tables,
                    'forms': processed_forms,
                },
                'layout': self._generate_layout_map(blocks),
                'confidence': confidence,
                'statistics': statistics,
                'processingTime': processing_time,
            }

    def _process_text_with_layout(self, text_blocks):
        """
        Enhanced text processing with layout preservation
        """
        if not text_blocks:
            return ''

        # Sort blocks by position (top to bottom, left to right)
        sorted_blocks = sorted(text_blocks, key=lambda x: (
            x.get('Geometry', {}).get('BoundingBox', {}).get('Top', 0),
            x.get('Geometry', {}).get('BoundingBox', {}).get('Left', 0)
        ))

        # Group by rows (similar Y positions)
        rows = self._group_blocks_by_row(sorted_blocks)

        # Process each row
        processed_lines = []
        for row in rows:
            # Sort blocks in row by X position
            sorted_row = sorted(row, key=lambda x: x.get('Geometry', {}).get('BoundingBox', {}).get('Left', 0))
            
            row_text = ' '.join([
                block.get('Text', '') 
                for block in sorted_row 
                if block.get('Text', '').strip()
            ])
            
            if row_text.strip():
                processed_lines.append(row_text)

        # Convert newlines to HTML br tags to match structured PDF processing
        return self.nl2br('\n'.join(processed_lines))

    def _group_blocks_by_row(self, blocks):
        """
        Group blocks by row (similar Y positions)
        """
        rows = []
        tolerance = 0.02  # Tolerance for considering blocks in the same row

        for block in blocks:
            if not block.get('Geometry', {}).get('BoundingBox'):
                continue

            block_top = block['Geometry']['BoundingBox']['Top']
            added_to_row = False

            for i, row in enumerate(rows):
                if not row:
                    continue
                    
                first_block_in_row = row[0]
                if not first_block_in_row.get('Geometry', {}).get('BoundingBox'):
                    continue

                row_top = first_block_in_row['Geometry']['BoundingBox']['Top']
                if abs(block_top - row_top) <= tolerance:
                    rows[i].append(block)
                    added_to_row = True
                    break

            if not added_to_row:
                rows.append([block])

        return rows

    def nl2br(self, s):
        """
        Convert newlines to HTML br tags to match structured PDF processing
        This ensures consistent line break handling across both extraction methods
        """
        return '<br />\n'.join(s.split('\n'))

    def _process_tables_enhanced(self, table_blocks, all_blocks):
        """
        Enhanced table processing
        """
        processed_tables = []
        
        for table_block in table_blocks:
            table_id = table_block['Id']

            # Get all cells in this table
            table_cells = [
                block for block in all_blocks 
                if block['BlockType'] == 'CELL' and 
                block.get('Relationships') and 
                any(rel['Type'] == 'CHILD' and table_id in rel['Ids'] 
                     for rel in block['Relationships'])
            ]

            if not table_cells:
                continue

            # Sort cells by position
            sorted_cells = self._sort_cells_by_position(table_cells)
            cell_rows = self._group_cells_by_row(sorted_cells)

            # Process each row
            table_rows = []
            for row in cell_rows:
                row_texts = []
                for cell in row:
                    cell_text = self._get_cell_text(cell, all_blocks)
                    row_texts.append(cell_text or '')
                table_rows.append('|'.join(row_texts))

            processed_tables.append({
                'id': table_id,
                'confidence': table_block.get('Confidence', 0),
                'rows': table_rows,
                'cellCount': len(table_cells),
                'rowCount': len(cell_rows),
            })

        return processed_tables

    def _process_forms_enhanced(self, form_blocks, all_blocks):
        """
        Enhanced form processing
        """
        key_value_pairs = []

        for block in form_blocks:
            if block.get('EntityTypes') and 'KEY' in block['EntityTypes']:
                key_text = self._get_block_text(block, all_blocks)
                value_block = self._find_value_block(block, all_blocks)
                value_text = self._get_block_text(value_block, all_blocks) if value_block else ''

                if key_text and value_text:
                    key_value_pairs.append({
                        'key': key_text.strip(),
                        'value': value_text.strip(),
                        'confidence': block.get('Confidence', 0),
                        'geometry': block.get('Geometry'),
                    })

        return key_value_pairs

    def _find_value_block(self, key_block, all_blocks):
        """
        Find value block for a key block
        """
        if not key_block.get('Relationships'):
            return None

        value_ids = []
        for rel in key_block['Relationships']:
            if rel['Type'] == 'VALUE':
                value_ids.extend(rel['Ids'])

        for block in all_blocks:
            if (block['BlockType'] == 'KEY_VALUE_SET' and 
                block.get('EntityTypes') and 
                'VALUE' in block['EntityTypes'] and 
                block['Id'] in value_ids):
                return block

        return None

    def _get_block_text(self, block, all_blocks):
        """
        Get text from a block
        """
        if not block or not block.get('Relationships'):
            return ''

        child_ids = []
        for rel in block['Relationships']:
            if rel['Type'] == 'CHILD':
                child_ids.extend(rel['Ids'])

        text_blocks = [
            b for b in all_blocks 
            if b['BlockType'] == 'LINE' and b['Id'] in child_ids
        ]

        return ' '.join([
            block.get('Text', '') 
            for block in text_blocks 
            if block.get('Text', '').strip()
        ])

    def _get_cell_text(self, cell, all_blocks):
        """
        Get text from a cell
        """
        return self._get_block_text(cell, all_blocks)

    def _sort_cells_by_position(self, cells):
        """
        Sort cells by position
        """
        return sorted(cells, key=lambda x: (
            x.get('Geometry', {}).get('BoundingBox', {}).get('Top', 0),
            x.get('Geometry', {}).get('BoundingBox', {}).get('Left', 0)
        ))

    def _group_cells_by_row(self, cells):
        """
        Group cells by row
        """
        rows = []
        tolerance = 0.02

        for cell in cells:
            if not cell.get('Geometry', {}).get('BoundingBox'):
                continue

            cell_top = cell['Geometry']['BoundingBox']['Top']
            added_to_row = False

            for i, row in enumerate(rows):
                if not row:
                    continue
                    
                first_cell_in_row = row[0]
                if not first_cell_in_row.get('Geometry', {}).get('BoundingBox'):
                    continue

                row_top = first_cell_in_row['Geometry']['BoundingBox']['Top']
                if abs(cell_top - row_top) <= tolerance:
                    rows[i].append(cell)
                    added_to_row = True
                    break

            if not added_to_row:
                rows.append([cell])

        return rows

    def _calculate_confidence(self, blocks, threshold=80):
        """
        Calculate confidence scores
        """
        confidences = [
            block.get('Confidence', 0) 
            for block in blocks 
            if block.get('Confidence', 0) > 0
        ]

        if not confidences:
            return {
                'average': 0,
                'minimum': 0,
                'maximum': 0,
                'lowConfidenceCount': 0,
                'totalBlocks': 0,
                'threshold': threshold,
            }

        average = sum(confidences) / len(confidences)
        low_confidence_blocks = [conf for conf in confidences if conf < threshold]

        return {
            'average': round(average, 2),
            'minimum': min(confidences),
            'maximum': max(confidences),
            'lowConfidenceCount': len(low_confidence_blocks),
            'totalBlocks': len(confidences),
            'threshold': threshold,
        }

    def _generate_layout_map(self, blocks):
        """
        Generate layout map for debugging
        """
        layout_map = []
        for block in blocks:
            geometry = block.get('Geometry', {}).get('BoundingBox')
            layout_item = {
                'id': block['Id'],
                'type': block['BlockType'],
                'text': block.get('Text', ''),
                'confidence': block.get('Confidence', 0),
                'geometry': None
            }
            
            if geometry:
                layout_item['geometry'] = {
                    'left': geometry['Left'],
                    'top': geometry['Top'],
                    'width': geometry['Width'],
                    'height': geometry['Height'],
                }
            
            layout_map.append(layout_item)
        
        return layout_map

    def extractPagesWithS3Url(self, s3_url):
        """
        Extract text from PDF using a single S3 URL - processes ENTIRE document
        """
        try:
            result = self.processDocumentWithS3Url(s3_url)
            self.logger.info(f'Successfully processed: {s3_url}')
            return result
        except Exception as e:
            self.logger.error(f'Failed to process S3 URL: {e}')
            raise

    def _write_output_files(self, processed_result):
        """
        Write output files for single or multi-page documents
        """
        if 'pages' in processed_result:
            # Multi-page document - write separate files for each page
            for page_data in processed_result['pages']:
                page_num = page_data['page']
                page_text = page_data['text']
                outfile = os.path.join(self.outdir, f"{page_num}.txt")
                with open(outfile, 'w', encoding='utf-8') as op:
                    op.write(page_text)
            
            self.logger.info(f'Document processed: {processed_result["totalPages"]} pages, '
                           f'{processed_result["overallStatistics"]["textBlocks"]} text blocks')
        else:
            # Single page document - write single file
            outfile = os.path.join(self.outdir, "1.txt")
            with open(outfile, 'w', encoding='utf-8') as op:
                op.write(processed_result['text'])
            
            self.logger.info(f'Single page document processed: {processed_result["statistics"]["textBlocks"]} text blocks')

    
